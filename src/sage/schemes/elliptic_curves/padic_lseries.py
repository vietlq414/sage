"""
p-adic L-functions of elliptic curves

AUTHORS:
   -- William Stein (2007-01-01): first version
   -- chris wuthrich (22/05/2007): changed minor issues and added supersingular things
                     (11/2008): added quadratic_twists
"""

######################################################################
#       Copyright (C) 2007 William Stein <wstein@gmail.com>
#
#  Distributed under the terms of the GNU General Public License (GPL)
#
#    This code is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    General Public License for more details.
#
#  The full text of the GPL is available at:
#
#                  http://www.gnu.org/licenses/
######################################################################


from sage.rings.integer_ring import   ZZ
from sage.rings.rational_field import QQ
from sage.rings.padics.factory import Qp, Zp
from sage.rings.infinity import infinity
from sage.rings.all import LaurentSeriesRing, PowerSeriesRing, PolynomialRing, Integers

from sage.rings.integer import Integer
from sage.rings.arith import valuation, binomial, kronecker_symbol, gcd, prime_divisors, valuation

from sage.structure.sage_object import SageObject

from sage.misc.all import verbose, denominator, get_verbose
from sage.databases.cremona import parse_cremona_label
from sage.schemes.elliptic_curves.constructor import EllipticCurve
import sage.rings.arith as arith

from sage.modules.free_module_element import vector
import sage.matrix.all as matrix
import monsky_washnitzer
# from sage.interfaces.all import gp
from sage.misc.functional import log

from sage.libs.cremona.newforms import ECModularSymbol
from sage.calculus.calculus import sqrt

class pAdicLseries(SageObject):
    r"""
    The p-adic L-series of an elliptic curve.

    EXAMPLES:
    An ordinary example::

        sage: e = EllipticCurve('389a')
        sage: L = e.padic_lseries(5)
        sage: L.series(0)
        Traceback (most recent call last):
        ...
        ValueError: n (=0) must be a positive integer
        sage: L.series(1)
        O(T^1)
        sage: L.series(2)
        O(5^4) + O(5)*T + (4 + O(5))*T^2 + (2 + O(5))*T^3 + (3 + O(5))*T^4 + O(T^5)
        sage: L.series(3, prec=10)
        O(5^5) + O(5^2)*T + (4 + 4*5 + O(5^2))*T^2 + (2 + 4*5 + O(5^2))*T^3 + (3 + O(5^2))*T^4 + (1 + O(5))*T^5 + (3*5 + O(5^2))*T^6 + (4 + 5 + O(5^2))*T^7 + (2 + 5 + O(5^2))*T^8 + O(5^2)*T^9 + O(T^10)
        sage: L.series(2,quadratic_twist=-3)
        2 + 4*5 + 4*5^2 + O(5^4) + O(5)*T + (1 + O(5))*T^2 + (4 + O(5))*T^3 + O(5)*T^4 + O(T^5)


    A prime p such that E[p] is reducible::

        sage: L = EllipticCurve('11a').padic_lseries(5)
        sage: L.series(1)
        5 + O(5^2) + O(T)
        sage: L.series(2)
        5 + 4*5^2 + O(5^3) + O(5^0)*T + O(5^0)*T^2 + O(5^0)*T^3 + O(5^0)*T^4 + O(T^5)
        sage: L.series(3)
        5 + 4*5^2 + 4*5^3 + O(5^4) + O(5)*T + O(5)*T^2 + O(5)*T^3 + O(5)*T^4 + O(T^5)

    the load-dumps test::

        sage: lp = EllipticCurve('11a').padic_lseries(5)
        sage: lp == loads(dumps(lp))
        True
    """
    def __init__(self, E, p, use_eclib=False, normalize='L_ratio'):
        r"""
        INPUT:

        -  ``E`` - an elliptic curve
        -  ``p`` - a prime of good reduction
        -  ``use_eclib`` - bool (default:False); whether or not to use
           John Cremona's eclib for the computation of modular
           symbols
        -  ``normalize`` - ``'L_ratio'`` (default), ``'period'`` or ``'none'``;
           this is describes the way the modular symbols
           are normalized. See ``modular_symbol`` of
           an elliptic curve over Q for more details.

        """
        self._E = E
        self._p = ZZ(p)
        self._normalize = normalize
        self._use_eclib = use_eclib
        if not self._p.is_prime():
            raise ValueError, "p (=%s) must be a prime"%p
        if E.conductor() % (self._p)**2 == 0:
            raise NotImplementedError, "p (=%s) must be a prime of semi-stable reduction"%p

        try :
            crla = E.label()
        except RuntimeError :
            print "Warning : Curve outside Cremona's table. Computations of modular symbol space might take very long !"

        self._modular_symbol = E.modular_symbol(sign=+1, use_eclib = use_eclib, normalize=normalize)

    def __add_negative_space(self):
        r"""
        This function add the attribute ``_negative_modular_symbol`` to the class. This may take time
        and will only be needed when twisting with negative fundamental discriminants.
        """
        if self._use_eclib:
            verbose('Currently there is no negative modular symbols in eclib, so we have to fall back on the implementation of modular symbols in sage')
            # once there is a eclib implementation of -1, this should be changed.
            self._negative_modular_symbol = self._E.modular_symbol(sign=-1, use_eclib = False, normalize=self._normalize)
        else:
            self._negative_modular_symbol = self._E.modular_symbol(sign=-1, use_eclib = False, normalize=self._normalize)

    def __cmp__(self,other):
        r"""
        Compare self and other.

        TESTS::
            sage: lp1 = EllipticCurve('11a1').padic_lseries(5)
            sage: lp2 = EllipticCurve('11a1').padic_lseries(7)
            sage: lp3 = EllipticCurve('11a2').padic_lseries(5)
            sage: lp1 == lp1
            True
            sage: lp1 == lp2
            False
            sage: lp1 == lp3
            False

        """
        c = cmp(type(self), type(other))
        if c:
            return c
        return cmp((self._E, self._p), (other._E, other._p))


    def elliptic_curve(self):
        r"""
        Return the elliptic curve to which this `p`-adic L-series is associated.

        EXAMPLES::

            sage: L = EllipticCurve('11a').padic_lseries(5)
            sage: L.elliptic_curve()
            Elliptic Curve defined by y^2 + y = x^3 - x^2 - 10*x - 20 over Rational Field
        """
        return self._E

    def prime(self):
        r"""
        Returns the prime `p` as in 'p-adic L-function'.

        EXAMPLES::

            sage: L = EllipticCurve('11a').padic_lseries(5)
            sage: L.prime()
            5
        """
        return self._p

    def _repr_(self):
        r"""
        Return print representation.

        EXAMPLES::

            sage: e = EllipticCurve('37a')
            sage: e.padic_lseries(3)
            3-adic L-series of Elliptic Curve defined by y^2 + y = x^3 - x over Rational Field
            sage: e.padic_lseries(3,normalize='none')
            3-adic L-series of Elliptic Curve defined by y^2 + y = x^3 - x over Rational Field (not normalized)
            sage: L = e.padic_lseries(3,normalize='none')
            sage: L.rename('(factor)*L_3(T)')
            sage: L
            (factor)*L_3(T)
        """
        s = "%s-adic L-series of %s"%(self._p, self._E)
        if not self._normalize == 'L_ratio':
            s += ' (not normalized)'
        return s

    def modular_symbol(self, r, sign=+1, quadratic_twist= +1):
        r"""
        Return the modular symbol evaluated at `r`.
        This is used to compute this `p`-adic
        L-series.

        Note that the normalisation is not correct at this
        stage: use ``_quotient_of periods_to_twist`` to correct.

        Note also that this function does not check if the condition
        on the quadratic_twist=D is satisfied. So the result will only
        be correct if for each prime `\ell` dividing `D`, we have
        `ord_{\ell(N)}<= ord_{\ell}(D)`, where `N` is the conductor of the curve.

        INPUT:

        -  ``r`` - a cusp given as either a rational number or oo

        -  ``sign`` - +1 (default) or -1 (only implemented without twists)

        -  ``quadratic_twist`` - a fundamental discriminant of a quardratic field or +1 (default)

        EXAMPLES::

			sage: E = EllipticCurve('11a1')
            sage: lp = E.padic_lseries(5)
            sage: [lp.modular_symbol(r) for r in [0,1/5,oo,1/11]]
            [1/5, 6/5, 0, 0]
            sage: [lp.modular_symbol(r,sign=-1) for r in [0,1/3,oo,1/7]]
            [0, 1, 0, -1]
            sage: [lp.modular_symbol(r,quadratic_twist=-20) for r in [0,1/5,oo,1/11]]
            [2, 2, 0, 1]

			sage: lpt = E.quadratic_twist(-3).padic_lseries(5)
			sage: et = E.padic_lseries(5)._quotient_of_periods_to_twist(-3)
			sage: lpt.modular_symbol(0) == lp.modular_symbol(0,quadratic_twist=-3)/et
			True

        """
        if quadratic_twist == +1 :
            if sign == +1 :
                return self._modular_symbol(r)
            elif sign == -1:
                try:
                    m = self._negative_modular_symbol
                except (KeyError, AttributeError):
                    if not hasattr(self, '_modular_symbol_negative'):
                        self.__add_negative_space()
                        m = self._negative_modular_symbol
                return m(r)
        else :
            D = quadratic_twist
            if sign == -1:
                raise NotImplementedError, "Quadratic twists for negative modular symbols are not yet implemented."
            if D > 0:
                m = self._modular_symbol
                s = +1
            else:
                try:
                    m = self._negative_modular_symbol
                except (KeyError, AttributeError):
                    if not hasattr(self, '_modular_symbol_negative'):
                        self.__add_negative_space()
                        m = self._negative_modular_symbol
                s = -1
            # without the ZZ here the u is treated as a 'int' and dividing by D gives 0
            # this only happens when it is called from __init__ (?)
            return s * sum([kronecker_symbol(D,u) * m(r+ZZ(u)/D) for u in range(1,abs(D))])


    def measure(self, a, n, prec, quadratic_twist=+1 ):
        r"""
        Return the measure on `\ZZ_p^*` defined by
           `
             \mu_{E,\alpha}^+ ( a + p^n \ZZ_p  ) =
                   \frac{1}{\alpha^n} \modsym{a}{p^n} - \frac{1}{\alpha^{n+1}} \modsym{a}{p^{n-1}}
           `
        that is used to define this `p`-adic L-function (at least when the reduction is good).

        The optional argument quadratic_twist replaces E by the twist in the above formula,
        but the twisted modular symbol is computed using a sum over modular symbols of `E`
        rather then finding the modular symbols for the twist.

        Note that the normalisation is not correct at this
        stage: use  ``_quotient_of periods`` and ``_quotient_of periods_to_twist``
        to correct.

        Note also that this function does not check if the condition
        on the ``quadratic_twist=D`` is satisfied. So the result will only
        be correct if for each prime `\ell` dividing `D`, we have
        `ord_{\ell}(N)<= ord_{\ell}(D)`, where `N` is the conductor of the curve.

        INPUT:

        -  ``a`` - an integer

        -  ``n`` - a non-negative integer

        -  ``prec`` - an integer

        -  ``quadratic_twist`` (default = 1) - a fundamental discriminant of a quadratic field,
           should be coprime to the conductor of `E`

        EXAMPLES::

            sage: E = EllipticCurve('37a')
            sage: L = E.padic_lseries(5)
            sage: L.measure(1,2, prec=9)
            2 + 3*5 + 4*5^3 + 2*5^4 + 3*5^5 + 3*5^6 + 4*5^7 + 4*5^8 + O(5^9)
            sage: L.measure(1,2, quadratic_twist=8,prec=15)
            O(5^15)
            sage: L.measure(1,2, quadratic_twist=-4,prec=15)
            4 + 4*5 + 4*5^2 + 3*5^3 + 2*5^4 + 5^5 + 3*5^6 + 5^8 + 2*5^9 + 3*5^12 + 2*5^13 + 4*5^14 + O(5^15)

            sage: E = EllipticCurve('11a1')
            sage: a = E.quadratic_twist(-3).padic_lseries(5).measure(1,2,prec=15)
            sage: b = E.padic_lseries(5).measure(1,2, quadratic_twist=-3,prec=15)
            sage: a == b/E.padic_lseries(5)._quotient_of_periods_to_twist(-3)
            True

        """

        if quadratic_twist > 0:
            s = +1
        else:
            s = -1
        try:
            p, alpha, z, w, f = self.__measure_data[(n,prec,s)]
        except (KeyError, AttributeError):
            if not hasattr(self, '__measure_data'):
                self.__measure_data = {}
            p = self._p
            alpha = self.alpha(prec=prec)
            z = 1/(alpha**n)
            w = p**(n-1)
            if s == +1 :
                f = self._modular_symbol
            else :
                try :
                    f = self._negative_modular_symbol
                except (KeyError, AttributeError):
                    if not hasattr(self, '_modular_symbol_negative'):
                        self.__add_negative_space()
                        f = self._negative_modular_symbol
            self.__measure_data[(n,prec,s)] = (p,alpha,z,w,f)

        if quadratic_twist == 1:
            if self._E.conductor() % p == 0:
                return z * f(a/(p*w))
            return z * f(a/(p*w)) - (z/alpha) * f(a/w)
        else:
            D = quadratic_twist
            chip = kronecker_symbol(D,p)
            if self._E.conductor() % p == 0:
                mu = chip**n * z * sum([kronecker_symbol(D,u) * f(a/(p*w)+ZZ(u)/D) for u in range(1,abs(D))])
            else:
                mu = chip**n * sum([kronecker_symbol(D,u) *(z * f(a/(p*w)+ZZ(u)/D) - chip *(z/alpha)* f(a/w+ZZ(u)/D)) for u in range(1,abs(D))])
            return s*mu

    def alpha(self, prec=20):
        r"""
        Return a `p`-adic root `\alpha` of the polynomial `x^2 - a_p x
        + p` with `ord_p(\alpha) < 1`.  In the ordinary case this is
        just the unit root.

        INPUT:
        -  ``prec`` - positive integer, the `p`-adic precision of the root.

        EXAMPLES:
        Consider the elliptic curve 37a::

            sage: E = EllipticCurve('37a')

        An ordinary prime::

            sage: L = E.padic_lseries(5)
            sage: alpha = L.alpha(10); alpha
            3 + 2*5 + 4*5^2 + 2*5^3 + 5^4 + 4*5^5 + 2*5^7 + 5^8 + 5^9 + O(5^10)
            sage: alpha^2 - E.ap(5)*alpha + 5
            O(5^10)

        A supersingular prime::

            sage: L = E.padic_lseries(3)
            sage: alpha = L.alpha(10); alpha
            (1 + O(3^10))*alpha
            sage: alpha^2 - E.ap(3)*alpha + 3
            (O(3^10))*alpha^2 + (O(3^11))*alpha + (O(3^11))

        A reducible prime::

            sage: L = EllipticCurve('11a').padic_lseries(5)
            sage: L.alpha(5)
            1 + 4*5 + 3*5^2 + 2*5^3 + 4*5^4 + O(5^5)
        """
        try:
            return self._alpha[prec]
        except AttributeError:
            self._alpha = {}
        except KeyError:
            pass
        E = self._E
        p = self._p
        a_p = E.ap(p)
        K = Qp(p, prec, print_mode='series')

        if E.conductor() % p == 0:
            self._alpha[prec] = K(a_p)
            return K(a_p)

        R = ZZ['x']
        f = R([p, -a_p, 1])
        if E.is_ordinary(p):
            G = f.factor_padic(p, prec+5)
            for pr, e in G:
                a = -pr[0]
                if a.valuation() < 1:
                    self._alpha[prec] = K(a)
                    return K(a)
            raise ValueError, "bug in p-adic L-function alpha"
        else: # supersingular case
            f = f.change_ring(Qp(p, prec, print_mode='series'))
            a = f.root_field('alpha', check_irreducible=False).gen()
            self._alpha[prec] = a
            return a

    def order_of_vanishing(self):
        r"""
        Return the order of vanishing of this `p`-adic L-series.

        The output of this function is provably correct, due to a
        theorem of Kato.  This function will terminate if and only if
        the Mazur-Tate-Teitelbaum analogue [MTT]_ of the BSD conjecture about
        the rank of the curve is true and the subgroup of elements of
        `p`-power order in the Shafarevich-Tate group of this curve is
        finite.  I.e. if this function terminates (with no errors!),
        then you may conclude that the `p`-adic BSD rank conjecture is
        true and that the `p`-part of Sha is finite.

        NOTE: currently `p` must be a prime of good ordinary reduction.

        EXAMPLES::

            sage: L = EllipticCurve('11a').padic_lseries(3)
            sage: L.order_of_vanishing()
            0
            sage: L = EllipticCurve('11a').padic_lseries(5)
            sage: L.order_of_vanishing()
            0
            sage: L = EllipticCurve('37a').padic_lseries(5)
            sage: L.order_of_vanishing()
            1
            sage: L = EllipticCurve('43a').padic_lseries(3)
            sage: L.order_of_vanishing()
            1
            sage: L = EllipticCurve('37b').padic_lseries(3)
            sage: L.order_of_vanishing()
            0

        We verify that Sha(E)(p) is finite for p=3,5,7 for the
        first curve of rank 2::

            sage: e = EllipticCurve('389a')
            sage: for p in primes(3,10):
            ...    print p, e.padic_lseries(p).order_of_vanishing()
            3 2
            5 2
            7 2
        """
        try:
            return self.__ord
        except AttributeError:
            pass

        if not self.is_ordinary():
            raise NotImplementedError
        E = self.elliptic_curve()
        if not E.is_good(self.prime()):
            raise ValueError, "prime must be of good reduction"
        r = E.rank()
        n = 1
        while True:
            f = self.series(n)
            v = f.valuation()
            if v < r:
                raise RuntimeError, "while computing p-adic order of vanishing, got a contradiction: the curve is %s, the curve has rank %s, but the p-adic L-series vanishes to order <= %s"%(E, r, v)
            if v == r:
                self.__ord = v
                return v
            n += 1


    def _c_bounds(self, n):
        raise NotImplementedError

    def _prec_bounds(self, n,prec):
        raise NotImplementedError

    def teichmuller(self, prec):
        r"""
        Return Teichmuller lifts to the given precision.

        INPUT:

        - ``prec`` - a positive integer.

        OUTPUT:

        - a list of `p`-adic numbers, the cached Teichmuller lifts

        EXAMPLES::

            sage: L = EllipticCurve('11a').padic_lseries(7)
            sage: L.teichmuller(1)
            [0, 1, 2, 3, 4, 5, 6]
            sage: L.teichmuller(2)
            [0, 1, 30, 31, 18, 19, 48]
        """
        p = self._p
        K = Qp(p, prec, print_mode='series')
        return [Integer(0)] + \
               [a.residue(prec).lift() for a in K.teichmuller_system()]

    def _e_bounds(self, n, prec):
        p = self._p
        prec = max(2,prec)
        R = PowerSeriesRing(ZZ,'T',prec+1)
        T = R(R.gen(),prec +1)
        w = (1+T)**(p**n) - 1
        return [infinity] + [valuation(w[j],p) for j in range(1,min(w.degree()+1,prec))]

    def _get_series_from_cache(self, n, prec, D):
        try:
            return self.__series[(n,prec,D)]
        except AttributeError:
            self.__series = {}
        except KeyError:
            for _n, _prec, _D in self.__series.keys():
                if _n == n and _D == D and _prec <= prec:
                    return self.__series[(_n,_prec,_D)].add_bigoh(prec)
        return None

    def _set_series_in_cache(self, n, prec, D, f):
        self.__series[(n,prec,D)] = f


    def _quotient_of_periods_to_twist(self,D):
        r"""
        For a fundamental discriminant `D` of a quadratic number field this computes the constant `\eta` such that
        `\sqrt{D}\cdot\Omega_{E_D}^{+} =\eta\cdot \Omega_E^{sign(D)}`. As in [MTT]_ page 40.
        This is either 1 or 2 unless the condition on the twist is not satisfied, e.g. if we are 'twisting back'
        to a semi-stable curve.

        .. [MTT] Mazur, Tate, Teitelbaum. `p`-adic BSD

        No check on precision is made, so this may fail for huge `D`.

        EXAMPLES::

            sage: E = EllipticCurve('37b1')
            sage: lp = E.padic_lseries(3)
            sage: lp._quotient_of_periods_to_twist(-20)
            1
            sage: lp._quotient_of_periods_to_twist(-4)
            1
            sage: lp._quotient_of_periods_to_twist(-3)
            1
            sage: lp._quotient_of_periods_to_twist(-8)
            2
            sage: lp._quotient_of_periods_to_twist(8)
            2
            sage: lp._quotient_of_periods_to_twist(5)
            1
            sage: lp._quotient_of_periods_to_twist(12)
            1

            sage: E = EllipticCurve('11a1')
            sage: Et = E.quadratic_twist(-3)
            sage: lpt = Et.padic_lseries(5)
            sage: lpt._quotient_of_periods_to_twist(-3)
            6

        """
        # This funciton does not depend on p and could be moved out of this file but it is needed only here

        # Note that the number of real components does not change by twisting.
        if D == 1:
            return 1
        if D > 1:
            Et = self._E.quadratic_twist(D)
            qt = Et.period_lattice().basis()[0]/self._E.period_lattice().basis()[0]
            qt *= sqrt(qt.parent()(D))
        else:
            Et = self._E.quadratic_twist(D)
            qt = Et.period_lattice().basis()[0]/self._E.period_lattice().basis()[1].imag()
            qt *= sqrt(qt.parent()(-D))
        verbose('the real approximation is %s'%qt)
        # we know from MTT that the result has a denominator 1
        return QQ(int(round(8*qt)))/8


class pAdicLseriesOrdinary(pAdicLseries):
    def series(self, n=2, quadratic_twist=+1, prec=5):
        r"""
        Return the `n`-th approximation to the `p`-adic L-series as
        a power series in `T` (corresponding to `\gamma-1` with
        `\gamma=1+p` as a generator of `1+p\mathbb{Z}_p`).  Each
        coefficient is a `p`-adic number whose precision is provably
        correct.

        Here the normalization of the `p`-adic L-series is chosen
        such that `L_p(E,1) = (1-1/\alpha)^2 L(E,1)/\Omega_E`
        where `\alpha` is the unit root of the characteristic
        polynomial of Frobenius on `T_pE` and `\Omega_E` is the
        Neron period of `E`.

        INPUT:

        -  ``n`` - (default: 2) a positive integer

        -  ``quadratic_twist`` - (default: +1) a fundamental discriminant
           of a qudratic field, coprime to the
           conductor of the curve
        -  ``prec`` - (default: 5) maxima number of terms of the series
           to compute; to compute as many as possible just
           give a very large number for prec; the result will
           still be correct.

        ALIAS: power_series is identical to series.

        EXAMPLES:
        We compute some `p`-adic L-functions associated to the elliptic
        curve 11a::

            sage: E = EllipticCurve('11a')
            sage: p = 3
            sage: E.is_ordinary(p)
            True
            sage: L = E.padic_lseries(p)
            sage: L.series(3)
            2 + 3 + 3^2 + 2*3^3 + O(3^5) + (1 + 3 + O(3^2))*T + (1 + 2*3 + O(3^2))*T^2 + O(3)*T^3 + (2*3 + O(3^2))*T^4 + O(T^5)


        Another example at a prime of bad reduction, where the
        `p`-adic L-function has an extra 0 (compared to the non
        `p`-adic L-function)::

            sage: E = EllipticCurve('11a')
            sage: p = 11
            sage: E.is_ordinary(p)
            True
            sage: L = E.padic_lseries(p)
            sage: L.series(2)
            O(11^4) + (10 + O(11))*T + (6 + O(11))*T^2 + (2 + O(11))*T^3 + (5 + O(11))*T^4 + O(T^5)

        We compute a `p`-adic L-function that vanishes to order 2::

            sage: E = EllipticCurve('389a')
            sage: p = 3
            sage: E.is_ordinary(p)
            True
            sage: L = E.padic_lseries(p)
            sage: L.series(1)
            O(T^1)
            sage: L.series(2)
            O(3^4) + O(3)*T + (2 + O(3))*T^2 + O(T^3)
            sage: L.series(3)
            O(3^5) + O(3^2)*T + (2 + 2*3 + O(3^2))*T^2 + (2 + O(3))*T^3 + (1 + 3 + O(3^2))*T^4 + O(T^5)

        Rather than computing the `p`-adic L-function for the curve '15523a1', one can
        compute it as a quadratic_twist::

            sage: E = EllipticCurve('43a1')
            sage: lp = E.padic_lseries(3)
            sage: lp.series(2,quadratic_twist=-19)
            2 + 2*3 + 2*3^2 + O(3^4) + (1 + O(3))*T + (1 + O(3))*T^2 + O(T^3)
            sage: E.quadratic_twist(-19).label()    #optional --- since the conductor is greater than 10000, this needs the optional package 'database_cremona_ellcurve-20071019'
            '15523a1'

        This proves that the rank of '15523a1' is zero, even if mwrank can not determine this.

        """
        n = ZZ(n)
        if n < 1:
            raise ValueError, "n (=%s) must be a positive integer"%n

        # check if the conditions on quadratic_twist are satisfied
        D = ZZ(quadratic_twist)
        if D != 1:
            if D % 4 == 0:
                d = D//4
                if not d.is_squarefree() or d % 4 == 1:
                    raise ValueError, "quadratic_twist (=%s) must be a fundamental discriminant of a quadratic field"%D
            else:
                if not D.is_squarefree() or D % 4 != 1:
                    raise ValueError, "quadratic_twist (=%s) must be a fundamental discriminant of a quadratic field"%D
            if gcd(D,self._p) != 1:
                raise ValueError, "quadratic twist (=%s) must be coprime to p (=%s) "%(D,self._p)
            if gcd(D,self._E.conductor())!= 1:
                for ell in prime_divisors(D):
                    if valuation(self._E.conductor(),ell) > valuation(D,ell) :
                        raise ValueError, "can not twist a curve of conductor (=%s) by the quadratic twist (=%s)."%(self._E.conductor(),D)


        p = self._p
        if p == 2 and self._normalize :
            print 'Warning : For p=2 the normalization might not be correct !'
        #verbose("computing L-series for p=%s, n=%s, and prec=%s"%(p,n,prec))

        bounds = self._prec_bounds(n,prec)
        padic_prec = max(bounds[1:]) + 5
        verbose("using p-adic precision of %s"%padic_prec)

        res_series_prec = min(p**(n-1), prec)
        verbose("using series precision of %s"%res_series_prec)

        ans = self._get_series_from_cache(n, res_series_prec,D)
        if not ans is None:
            verbose("found series in cache")
            return ans

        K = QQ
        gamma = K(1 + p)
        R = PowerSeriesRing(K,'T',res_series_prec)
        T = R(R.gen(),res_series_prec )
        L = R(0)
        one_plus_T_factor = R(1)
        gamma_power = K(1)
        teich = self.teichmuller(padic_prec)
        p_power = p**(n-1)

        verbose("Now iterating over %s summands"%((p-1)*p_power))
        verbose_level = get_verbose()
        count_verb = 0
        for j in range(p_power):
            s = K(0)
            if verbose_level >= 2 and j/p_power*100 > count_verb + 3:
                verbose("%.2f percent done"%(float(j)/p_power*100))
                count_verb += 3
            for a in range(1,p):
                b = teich[a] * gamma_power
                s += self.measure(b, n, padic_prec,quadratic_twist=D).lift()
            L += s * one_plus_T_factor
            one_plus_T_factor *= 1+T
            gamma_power *= gamma

        verbose("the series before adjusting the precision is %s"%L)
        # Now create series but with each coefficient truncated
        # so it is proven correct:
        K = Qp(p, padic_prec, print_mode='series')
        R = PowerSeriesRing(K,'T',res_series_prec)
        L = R(L,res_series_prec)
        aj = L.list()
        if len(aj) > 0:
            aj = [aj[0].add_bigoh(padic_prec-2)] + [aj[j].add_bigoh(bounds[j]) for j in range(1,len(aj))]
        L = R(aj,res_series_prec )

        L /= self._quotient_of_periods_to_twist(D)*self._E.real_components()

        self._set_series_in_cache(n, res_series_prec, D, L)

        return L

    power_series = series


    def is_ordinary(self):
        """
        Return True if the elliptic that this L-function is attached
        to is ordinary.

        EXAMPLES::

            sage: L = EllipticCurve('11a').padic_lseries(5)
            sage: L.is_ordinary()
            True
        """
        return True

    def is_supersingular(self):
        """
        Return True if the elliptic that this L function is attached
        to is supersingular.

        EXAMPLES::

            sage: L = EllipticCurve('11a').padic_lseries(5)
            sage: L.is_supersingular()
            False
        """
        return False

    def _c_bound(self):
        try:
            return self.__c_bound
        except AttributeError:
            pass
        E = self._E
        p = self._p
        if E.is_irreducible(p):
            ans = 0
        else:
            m = E.modular_symbol_space(sign=1)
            b = m.boundary_map().codomain()
            C = b._known_cusps()  # all known, since computed the boundary map
            ans = max([valuation(self.modular_symbol(a).denominator(), p) for a in C])
        self.__c_bound = ans
        return ans

    def _prec_bounds(self, n, prec):
        p = self._p
        e = self._e_bounds(n-1, prec)
        c = self._c_bound()
        return [e[j] - c for j in range(len(e))]


class pAdicLseriesSupersingular(pAdicLseries):
    def series(self, n=3, quadratic_twist = +1, prec=5):
        r"""
        Return the `n`-th approximation to the `p`-adic L-series as a
        power series in `T` (corresponding to `\gamma-1` with
        `\gamma=1+p` as a generator of `1+p\mathbb{Z}_p`).  Each
        coefficient is an element of a quadratic extension of the `p`-adic
        number whose precision is probably correct.

        Here the normalization of the `p`-adic L-series is chosen
        such that `L_p(E,1) = (1-1/\alpha)^2 L(E,1)/\Omega_E`
        where `\alpha` is the unit root of the characteristic
        polynomial of Frobenius on `T_pE` and `\Omega_E` is the
        Neron period of `E`.

        INPUT:

        - ``n`` - (default: 3) a positive integer

        - ``prec`` - (default: 5) maxima number of terms of the series
          to compute; to compute as many as possible just
          give a very large number for prec; the result will
          still be correct.

        ALIAS: power_series is identical to series.

        EXAMPLES:
        A superingular example, where we must compute to higher precision to see anything::

            sage: e = EllipticCurve('37a')
            sage: L = e.padic_lseries(3); L
            3-adic L-series of Elliptic Curve defined by y^2 + y = x^3 - x over Rational Field
            sage: L.series(2)
            O(T^3)
            sage: L.series(4)         # takes a long time (several seconds)
            (O(3))*alpha + (O(3^2)) + ((O(3^-1))*alpha + (2*3^-1 + O(3^0)))*T + ((O(3^-1))*alpha + (2*3^-1 + O(3^0)))*T^2 + ((O(3^-2))*alpha + (O(3^-1)))*T^3 + ((O(3^-1))*alpha + (3^-1 + O(3^0)))*T^4 + O(T^5)
            sage: L.alpha(2).parent()
            Univariate Quotient Polynomial Ring in alpha over 3-adic Field with capped
            relative precision 2 with modulus (1 + O(3^2))*x^2 + (3 + O(3^3))*x + (3 + O(3^3))
        """
        n = ZZ(n)
        if n < 1:
            raise ValueError, "n (=%s) must be a positive integer"%n
#        if quadratic_twist != +1 :
#            raise NotImplementedError, "twists are not implemented for supersingular primes, so far."

        # check if the conditions on quadratic_twist are satisfied
        D = quadratic_twist
        if D != 1:
            if D % 4 == 0:
                d = D//4
                if not d.is_squarefree() or d % 4 == 1:
                    raise ValueError, "quadratic_twist (=%s) must be a fundamental discriminant of a quadratic field"%D
            else:
                if not D.is_squarefree() or D % 4 != 1:
                    raise ValueError, "quadratic_twist (=%s) must be a fundamental discriminant of a quadratic field"%D
            if gcd(D,self._p*self._E.conductor()) != 1:
                raise ValueError, "quadratic twist (=%s) must be coprime to p (=%s) and the conductor of the curve (%s) "%(D,self._p,self._E.conductor())

        p = self._p
        if p == 2 and self._normalize :
            print 'Warning : for p == 2 the normalization might not be correct !'

        prec = min(p**(n-1), prec)
        bounds = self._prec_bounds(n,prec)
        padic_prec = max(sum(bounds[1:],[])) + 5
        verbose("using p-adic precision of %s"%padic_prec)
        ans = self._get_series_from_cache(n, prec, quadratic_twist)
        if not ans is None:
            verbose("found series in cache")
            return ans

        alpha = self.alpha(prec=padic_prec)
        K = alpha.parent()
        gamma = 1 + p
        R = PowerSeriesRing(K,'T',prec)
        T = R(R.gen(), prec)
        L = R(0)
        one_plus_T_factor = R(1)
        gamma_power = 1
        teich = self.teichmuller(padic_prec)

        verbose("Now iterating over %s summands"%((p-1)*p**(n-1)))
        verbose_level = get_verbose()
        count_verb = 0
        for j in range(p**(n-1)):
            s = K(0)
            if verbose_level >= 2 and j/p**(n-1)*100 > count_verb + 3:
                verbose("%.2f percent done"%(float(j)/p**(n-1)*100))
                count_verb += 3
            for a in range(1,p):
                b = teich[a] * gamma_power
                s += self.measure(b, n, padic_prec,quadratic_twist=D)
            L += s * one_plus_T_factor
            one_plus_T_factor *= 1+T
            gamma_power *= gamma

        # Now create series but with each coefficient truncated
        # so it is proven correct:
        L = R(L,prec)
        aj = L.list()
        if len(aj) > 0:
            bj = [aj[0][0].add_bigoh(padic_prec-2) + alpha * aj[0][1].add_bigoh(padic_prec-2)]
            bj += [aj[j][0].add_bigoh(bounds[j][0]) + alpha * aj[j][1].add_bigoh(bounds[j][1]) for j in range(1,len(aj))]
            L = R(bj, prec)
        L /= self._quotient_of_periods_to_twist(D)*self._E.real_components()
        self._set_series_in_cache(n, prec, quadratic_twist, L)
        return L

    power_series = series

    def is_ordinary(self):
        return False

    def is_supersingular(self):
        return True

    def _prec_bounds(self, n,prec):
        p = self._p
        e = self._e_bounds(n-1,prec)
        c0 = ZZ(n+2)/2
        c1 = ZZ(n+3)/2
        return [[infinity,infinity]] + [[(e[j] - c0).floor(), (e[j] - c1).floor()] for j in range(1,len(e))]


    def Dp_valued_series(self, n=3, quadratic_twist = +1, prec=5):
        r"""
        Returns a vector of two components which are p-adic power series.
        The answer v is such that
            `(1-\varphi)^(-2)* L_p(E,T) = v[1] * \omega + v[2] * \varphi(\omega)`
        as an element of the Dieudonne module `D_p(E) = H^1_{dR}(E/\QQ_p)` where
        `\omega` is the invariant differential and `\varphi` is the Frobenius on `D_p(E)`.
        According to the `p`-adic BSD this function has a zero of order
        rank(E(Q)) and it's leading term is
        ``#Sha(E/Q) * Tamagawa product / Torsion^2 * padic height regulator with values in D_p(E)``.


        INPUT:

        -  ``n`` - (default: 3) a positive integer
        -  ``prec`` - (default: 5) a positive integer

        EXAMPLES::

            sage: E = EllipticCurve('14a')
            sage: L = E.padic_lseries(5)
            sage: L.Dp_valued_series(4)
            (1 + 4*5 + 4*5^3 + O(5^4) + (4 + O(5))*T + (1 + O(5))*T^2 + (4 + O(5))*T^3 + (2 + O(5))*T^4 + O(T^5), O(5^4) + O(5)*T + O(5)*T^2 + O(5)*T^3 + (2 + O(5))*T^4 + O(T^5))
        """
        E = self._E
        p = self._p
        lps = self.series(n, quadratic_twist=quadratic_twist, prec=prec)

        # now split up the series in two lps = G + H * alpha
        R = lps.base_ring().base_ring() # Qp
        QpT , T = PowerSeriesRing(R,'T',prec).objgen()
        G = QpT([lps[n][0] for n in range(0,lps.prec())], prec)
        H = QpT([lps[n][1] for n in range(0,lps.prec())], prec)

        # now compute phi
        phi = matrix.matrix([[0,-1/p],[1,E.ap(p)/p]])
        lpv = vector([G  + (E.ap(p))*H  , - R(p) * H ])  # this is L_p
        eps = (1-phi)**(-2)
        resu = lpv*eps.transpose()
        return resu


    def frobenius(self, prec=20, method = "mw"):
        r"""
        This returns a geometric Frobenius `\varphi` on the Diedonne module `D_p(E)`
        with respect to the basis `\omega`, the invariant differential and `\eta=x\omega`.
        It satisfies  `phi^2 - a_p/p phi + 1/p = 0`.

        INPUT:
        -  ``prec`` - (default: 20) a positive integer
        -  ``method`` - either 'mw' (default) for Monsky-Washintzer
           or 'approx' for the method described by Bernardi and Perrin-Riou
           (much slower)


        EXAMPLES::

            sage: E = EllipticCurve('14a')
            sage: L = E.padic_lseries(5)
            sage: phi = L.frobenius(5)
            sage: phi
            [                  2 + 5^2 + 5^4 + O(5^5)    3*5^-1 + 3 + 5 + 4*5^2 + 5^3 + O(5^4)]
            [      3 + 3*5^2 + 4*5^3 + 3*5^4 + O(5^5) 3 + 4*5 + 3*5^2 + 4*5^3 + 3*5^4 + O(5^5)]
            sage: -phi^2
            [5^-1 + O(5^4)        O(5^4)]
            [       O(5^5) 5^-1 + O(5^4)]
        """
        E = self._E
        p = self._p
        if method != "mw" and method !="approx":
            raise ValueError, "Unknown method %s."%method
        if method == "approx":
            return self.__phi_bpr(prec=prec)
        if p < 4 and method == "mw":
            print "Warning: If this fails try again using method=\"approx\""
        Ew = E.integral_short_weierstrass_model()
        adjusted_prec = monsky_washnitzer.adjusted_prec(p, prec)
        modprecring = Integers(p**adjusted_prec)
        output_ring = Qp(p, prec)
        R, x = PolynomialRing(modprecring, 'x').objgen()
        Q = x**3 + modprecring(Ew.a4()) * x + modprecring(Ew.a6())
        trace = Ew.ap(p)
        fr = monsky_washnitzer.matrix_of_frobenius(Q, p, adjusted_prec, trace)
        fr = matrix.matrix(output_ring,2,2,fr)

        # return a vector for pari's ellchangecurve to pass from e1 to e2
        def isom(e1,e2):
            if not e1.is_isomorphic(e2):
                raise ValueError, "Curves must be isomorphic."
            usq = (e1.discriminant()/e2.discriminant()).nth_root(6)
            u = usq.sqrt()
            s = (u   *  e2.a1() - e1.a1() )/ZZ(2)
            r = (usq *  e2.a2() - e1.a2() + s**2 + e1.a1()*s)/ZZ(3)
            t = (u**3 * e2.a3() - e1.a3() - e1.a1()*r)/ZZ(2)
            return [u,r,s,t]

        v = isom(E,Ew)
        u = v[0]
        r = v[1]

        # change basis
        A = matrix.matrix([[u,-r/u],[0,1/u]])
        frn = A * fr * A**(-1)
        return 1/p*frn



    def __phi_bpr(self, prec=0):
        """
        Returns the phi using the definition of bernardi-perrin-riou on page 232.
        """
        E = self._E
        p = self._p
        if prec > 10:
            print "Warning: Very large value for the precision."
        if prec == 0:
            prec = floor((log(10000)/log(p)))
            verbose("prec set to %s"%prec)
        eh = E.formal()
        om = eh.differential(prec = p**prec+3)
        verbose("differential computed")
        xt = eh.x(prec=p**prec + 3)
        et = xt*om
        # c_(p^k) = cs[k] d...
        cs = [om[p**k-1] for k in range(0,prec+1)]
        ds = [et[p**k-1] for k in range(0,prec+1)]
        delta = 0
        dpr = 0
        gamma = 0
        dga = 0
        for k in range(1,prec+1):
            # this is the equation eq[0]*x+eq[1]*y+eq[2] == 0
            # such that delta_ = delta + d^dpr*x ...
            eq = [(p**dpr*cs[k]) % p**k,(-p**dga*ds[k]) % p**k , (delta*cs[k]-gamma*ds[k]-cs[k-1]) % p**k ]
            verbose("valuations : %s"%([x.valuation(p) for x in eq]))
            v = min([x.valuation(p) for x in eq])
            if v == infinity:
                verbose("no new information at step k=%s"%k)
            else:
                eq = [ZZ(x/p**v) for x in eq]
                verbose("renormalised eq mod p^%s is now %s"%(k-v,eq))
                if eq[0].valuation(p) == 0:
                    l = min(eq[1].valuation(p),k-v)
                    if l == 0:
                        verbose("not uniquely determined at step k=%s"%k)
                    else:
                        ainv = eq[0].inverse_mod(p**l)
                        delta = delta - eq[2]*ainv*p**dpr
                        dpr = dpr + l
                        delta = delta % p**dpr
                        verbose("delta_prec increased to %s\n delta is now %s"%(dpr,delta))
                elif eq[1].valuation(p) == 0:
                    l = min(eq[0].valuation(p),k-v)
                    ainv = eq[1].inverse_mod(p**l)
                    gamma = gamma - eq[2]*ainv*p**dga
                    dga = dga + l
                    gamma = gamma % p**dga
                    verbose("gamma_prec increased to %s\n gamma is now %s"%(dga,gamma))
                else:
                    raise RuntimeError,  "Bug: no delta or gamma can exist"

        # end of approximation of delta and gamma
        R = Qp(p,max(dpr,dga)+1)
        delta = R(delta,absprec=dpr)
        gamma = R(gamma,absprec=dga)
        verbose("result delta = %s\n      gamma = %s\n check : %s"%(delta,gamma, [Qp(3,k)(delta * cs[k] - gamma * ds[k] - cs[k-1]) for k in range(1,prec+1)] ))
        a = delta
        c = -gamma
        d = E.ap(p) - a
        b = (-1/p+a*d)/c
        phi = matrix.matrix([[a,b],[c,d]])
        return phi


    def bernardi_sigma_function(self, prec=20):
        r"""
        Return the  `p`-adic sigma function of Bernardi in terms of `z = log(t)`.
        This is the same as ``padic_sigma`` with ``E2 = 0``.

        EXAMPLES::

            sage: E = EllipticCurve('14a')
            sage: L = E.padic_lseries(5)
            sage: L.bernardi_sigma_function(5) # Todo: some sort of consistency check!?
            z + 1/24*z^3 + 29/384*z^5 - 8399/322560*z^7 - 291743/92897280*z^9 - 4364831/5225472*z^10 + 2172371753/955514880*z^11 - 17875714529/6897623040*z^12 + 2839176621047/1605264998400*z^13 + 32012675789849/10042939146240*z^14 - 367444910151047/89894839910400*z^15 + 973773806885959/241030539509760*z^16 - 33997971208432501/17259809262796800*z^17 - 10331978660756704339/842918229599846400*z^18 + 18601407947897364480389/950670294194847744000*z^19 - 118837570440101901119321/8071784966648129126400*z^20 + O(z^21)
        """
        E = self._E
        p = self._p

        Eh = E.formal()
        lo = Eh.log(prec + 5)
        F = lo.reversion()

        S = LaurentSeriesRing(QQ,'z')
        z = S.gen()
        F = F(z)
        xofF = Eh.x(prec + 2)(F)
        #r =  ( E.a1()**2 + 4*E.a2() ) / ZZ(12)
        g = (1/z**2 - xofF ).power_series()
        h = g.integral().integral()
        sigma_of_z = z.power_series() * h.exp()

        return sigma_of_z


    def Dp_valued_height(self,prec=20):
        r"""
        Returns the canonical `p`-adic height with values in the Dieudonne module `D_p(E)`.
        It is defined to be
            `h_{\eta} \cdot \omega - h_{\omega} \cdot \eta`
        where `h_{\eta}` is made out of the sigma function of Bernardi and
        `h_{\omega}` is `-log^2`.
        The answer ``v`` is given as ``v[1]*omega + v[2]*eta``.
        The coordinates of ``v`` are dependent of the
        Weierstrass equation.

        EXAMPLES::

            sage: E = EllipticCurve('53a')
            sage: L = E.padic_lseries(5)
            sage: h = L.Dp_valued_height(7)
            sage: h(E.gens()[0])
            (3*5 + 5^2 + 2*5^3 + 3*5^4 + 4*5^5 + 5^6 + 5^7 + O(5^8), 5^2 + 4*5^4 + 2*5^7 + 3*5^8 + O(5^9))
        """
        E = self._E
        p = self._p
        Ehat = E.formal()
        elog = Ehat.log(prec + Integer(3))

        # we will have to do it properly with David Harvey's _multiply_point()
        n = arith.LCM(E.tamagawa_numbers())
        n = arith.LCM(n, E.Np(p)) # allowed here because E has good reduction at p

        if p < 5:
            phi = self.frobenius(min(6,prec),method="approx")
        else:
            phi = self.frobenius(prec+2,method="mw")

        def height(P,check=True):
            if P.is_finite_order():
                return Qp(p,prec)(0)
            if check:
                assert P.curve() == E, 'the point P must lie on the curve from which the height function was created'

            Q = n * P
            tt = - Q[0]/Q[1]
            R = Qp(p,prec+5)
            tt = R(tt)
            zz = elog(tt)

            homega = -zz**2/n**2

            eQ = denominator(Q[1])/denominator(Q[0])
            si = self.bernardi_sigma_function(prec=prec+4)
            heta =  2 * log(si(zz)/eQ) / n**2

            R = Qp(p,prec)

            return vector([-R(heta),R(homega)])

        return height



    def Dp_valued_regulator(self,prec=20,v1=0,v2=0):
        r"""
        Returns the canonical `p`-adic regulator with values in the Dieudonne module `D_p(E)`
        as defined by Perrin-Riou using the `p`-adic height with values in `D_p(E)`.
        The result is written in the basis `\omega`, `\varphi(\omega)`, and hence the
        coordinates of the result are independent of the chosen Weierstrass equation.

        NOTE: The definition here is corrected with repect to Perrin-Riou's article [PR]_
        .. [PR] Arithmetique des courbes elliptiques a reduction supersinguliere en `p`'.


        EXAMPLES::

            sage: E = EllipticCurve('43a')
            sage: L = E.padic_lseries(7)
            sage: L.Dp_valued_regulator(7)
            (5*7 + 6*7^2 + 4*7^3 + 4*7^4 + 7^5 + 4*7^7 + O(7^8), 4*7^2 + 2*7^3 + 3*7^4 + 7^5 + 6*7^6 + 4*7^7 + O(7^8))
        """

        p = self._p
        E = self._E

        h =  self.Dp_valued_height(prec=prec)

        # this is the height_{v} (P) for a v in D_p
        def hv(vec,P):
            hP = h(P)
            return - vec[0]*hP[1] +vec[1]*hP[0]

        #    def hvpairing(vec,P,Q):
        #        return (hv(vec,    P+Q) - hv(vec,P)-hv(vec,Q))/2
        K = Qp(p, prec)

        if v1 ==0 and v2 ==0 :
            v1 = vector([K(0),K(1)])  # that is eta
            v2 = vector([K(-1),K(1)])  # and this is eta-omega.
        #                      the rest should not depend on this choice
        #                      as long as it is outside Q_p * omega

        rk = E.rank()
        if rk == 0:
            return vector([K(1),K(0)])


        basis = E.gens()

        def regv(vec):
            M = matrix.matrix(K,rk,rk,0)
            point_height = [hv(vec,P) for P in basis]
            for i in range(rk):
                for j in range(i+1, rk):
                    M[i, j] = M[j, i] = (hv(vec,basis[i] + basis[j])- point_height[i] - point_height[j] )/2
            for i in range(rk):
                M[i,i] = point_height[i]

            return M.determinant()


        def Dp_pairing(vec1,vec2):
            return (vec1[0]*vec2[1]-vec1[1]*vec2[0])

        omega_vec = vector([K(1),K(0)])

        # note the correction here with respect to Perrin-Riou's definition.
        # only this way the result will be indep of the choice of v1 and v2.
        reg1 = regv(v1)/Dp_pairing(omega_vec,v1)**(rk-1)

        reg2 = regv(v2)/Dp_pairing(omega_vec,v2)**(rk-1)


        # the regulator in the basis omega,eta
        reg_oe = (reg1 * v2 - reg2 * v1 ) / Dp_pairing(v2,v1)

        if p < 5:
            phi = self.frobenius(min(6,prec),method="approx")
        else:
            phi = self.frobenius(prec+2,method="mw")

        c = phi[1,0]  # this is the 'period' [omega,phi(omega)]
        a = phi[0,0]

        return vector([reg_oe[0] - a/c*reg_oe[1],reg_oe[1]/c])

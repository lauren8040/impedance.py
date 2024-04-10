import numpy as np
from scipy.special import iv
from sympy import symbols,solve,Eq,evalf
from scipy.optimize import fsolve

class ElementError(Exception):
    ...


class OverwriteError(ElementError):
    ...


def element(num_params, units, overwrite=False):
    """decorator to store metadata for a circuit element

    Parameters
    ----------
    num_params : int
        number of parameters for an element
    units : list of str
        list of units for the element parameters
    overwrite : bool (default False)
        if true, overwrites any existing element; if false,
        raises OverwriteError if element name already exists.
    """

    def decorator(func):
        def wrapper(p, f):
            typeChecker(p, f, func.__name__, num_params)
            return func(p, f)

        wrapper.num_params = num_params
        wrapper.units = units
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        global circuit_elements
        if func.__name__ in ["s", "p"]:
            raise ElementError("cannot redefine elements 's' (series)" +
                               "or 'p' (parallel)")
        elif func.__name__ in circuit_elements and not overwrite:
            raise OverwriteError(
                f"element {func.__name__} already exists. " +
                "If you want to overwrite the existing element," +
                "use `overwrite=True`."
            )
        else:
            circuit_elements[func.__name__] = wrapper

        return wrapper

    return decorator


def s(series):
    """sums elements in series

    Notes
    ---------
    .. math::
        Z = Z_1 + Z_2 + ... + Z_n

    """
    z = len(series[0]) * [0 + 0 * 1j]
    for elem in series:
        z += elem
    return z


def p(parallel):
    """adds elements in parallel

    Notes
    ---------
    .. math::

        Z = \\frac{1}{\\frac{1}{Z_1} + \\frac{1}{Z_2} + ... + \\frac{1}{Z_n}}

    """
    z = len(parallel[0]) * [0 + 0 * 1j]
    for elem in parallel:
        z += 1 / elem
    return 1 / z


# manually add parallel and series operators to circuit elements w/o metadata
# populated by the element decorator -
# this maps ex. 'R' to the function R to always give us a list of
# active elements in any context
circuit_elements = {"s": s, "p": p}


@element(num_params=1, units=["Ohm"])
def R(p, f):
    """defines a resistor

    Notes
    ---------
    .. math::

        Z = R

    """
    R = p[0]
    Z = np.array(len(f) * [R])
    return Z


@element(num_params=1, units=["F"])
def C(p, f):
    """defines a capacitor

    .. math::

        Z = \\frac{1}{C \\times j 2 \\pi f}

    """
    omega = 2 * np.pi * np.array(f)
    C = p[0]
    Z = 1.0 / (C * 1j * omega)
    return Z


@element(num_params=1, units=["H"])
def L(p, f):
    """defines an inductor

    .. math::

        Z = L \\times j 2 \\pi f

    """
    omega = 2 * np.pi * np.array(f)
    L = p[0]
    Z = L * 1j * omega
    return Z


@element(num_params=1, units=["Ohm sec^-1/2"])
def W(p, f):
    """defines a semi-infinite Warburg element

    Notes
    -----
    .. math::

        Z = \\frac{A_W}{\\sqrt{ 2 \\pi f}} (1-j)
    """
    omega = 2 * np.pi * np.array(f)
    Aw = p[0]
    Z = Aw * (1 - 1j) / np.sqrt(omega)
    return Z


@element(num_params=2, units=["Ohm", "sec"])
def Wo(p, f):
    """defines an open (finite-space) Warburg element

    Notes
    ---------
    .. math::
        Z = \\frac{Z_0}{\\sqrt{ j \\omega \\tau }}
        \\coth{\\sqrt{j \\omega \\tau }}

    where :math:`Z_0` = p[0] (Ohms) and
    :math:`\\tau` = p[1] (sec) = :math:`\\frac{L^2}{D}`

    """
    omega = 2 * np.pi * np.array(f)
    Z0, tau = p[0], p[1]
    Z = Z0 / (np.sqrt(1j * omega * tau) * np.tanh(np.sqrt(1j * omega * tau)))
    return Z  # Zw(omega)


@element(num_params=2, units=["Ohm", "sec"])
def Ws(p, f):
    """defines a short (finite-length) Warburg element

    Notes
    ---------
    .. math::
        Z = \\frac{Z_0}{\\sqrt{ j \\omega \\tau }}
        \\tanh{\\sqrt{j \\omega \\tau }}

    where :math:`Z_0` = p[0] (Ohms) and
    :math:`\\tau` = p[1] (sec) = :math:`\\frac{L^2}{D}`

    """
    omega = 2 * np.pi * np.array(f)
    Z0, tau = p[0], p[1]
    Z = Z0 * np.tanh(np.sqrt(1j * omega * tau)) / np.sqrt(1j * omega * tau)
    return Z


@element(num_params=2, units=["Ohm^-1 sec^a", ""])
def CPE(p, f):
    """defines a constant phase element

    Notes
    -----
    .. math::

        Z = \\frac{1}{Q \\times (j 2 \\pi f)^\\alpha}

    where :math:`Q` = p[0] and :math:`\\alpha` = p[1].
    """
    omega = 2 * np.pi * np.array(f)
    Q, alpha = p[0], p[1]
    Z = 1.0 / (Q * (1j * omega) ** alpha)
    return Z


@element(num_params=2, units=["H sec", ""])
def La(p, f):
    """defines a modified inductance element as represented in [1]

    Notes
    -----
    .. math::

        Z = L \\times (j 2 \\pi f)^\\alpha

    where :math:`L` = p[0] and :math:`\\alpha` = p[1]

    [1] `EC-Lab Application Note 42, BioLogic Instruments (2019)
    <https://www.biologic.net/documents/battery-eis-modified-inductance-element-electrochemsitry-application-note-42>`_.
    """
    omega = 2 * np.pi * np.array(f)
    L, alpha = p[0], p[1]
    Z = (L * 1j * omega) ** alpha
    return Z


@element(num_params=2, units=["Ohm", "sec"])
def G(p, f):
    """defines a Gerischer Element as represented in [1]

    Notes
    ---------
    .. math::

        Z = \\frac{R_G}{\\sqrt{1 + j \\, 2 \\pi f \\, t_G}}

    where :math:`R_G` = p[0] and :math:`t_G` = p[1]

    Gerischer impedance is also commonly represented as [2]:

    .. math::

        Z = \\frac{Z_o}{\\sqrt{K+ j \\, 2 \\pi f}}

    where :math:`Z_o = \\frac{R_G}{\\sqrt{t_G}}`
    and :math:`K = \\frac{1}{t_G}`
    with units :math:`\\Omega sec^{1/2}` and
    :math:`sec^{-1}` , respectively.

    [1] Y. Lu, C. Kreller, and S.B. Adler,
    Journal of The Electrochemical Society, 156, B513-B525 (2009)
    `doi:10.1149/1.3079337
    <https://doi.org/10.1149/1.3079337>`_.

    [2] M. González-Cuenca, W. Zipprich, B.A. Boukamp,
    G. Pudmich, and F. Tietz, Fuel Cells, 1,
    256-264 (2001) `doi:10.1016/0013-4686(93)85083-B
    <https://doi.org/10.1016/0013-4686(93)85083-B>`_.
    """
    omega = 2 * np.pi * np.array(f)
    R_G, t_G = p[0], p[1]
    Z = R_G / np.sqrt(1 + 1j * omega * t_G)
    return Z


@element(num_params=3, units=["Ohm", "sec", ""])
def Gs(p, f):
    """defines a finite-length Gerischer Element as represented in [1]

    Notes
    ---------
    .. math::

        Z = \\frac{R_G}{\\sqrt{1 + j \\, 2 \\pi f \\, t_G} \\,
        tanh(\\phi \\sqrt{1 + j \\, 2 \\pi f \\, t_G})}

    where :math:`R_G` = p[0], :math:`t_G` = p[1] and :math:`\\phi` = p[2]

    [1] R.D. Green, C.C Liu, and S.B. Adler,
    Solid State Ionics, 179, 647-660 (2008)
    `doi:10.1016/j.ssi.2008.04.024
    <https://doi.org/10.1016/j.ssi.2008.04.024>`_.
    """
    omega = 2 * np.pi * np.array(f)
    R_G, t_G, phi = p[0], p[1], p[2]
    Z = R_G / (
        np.sqrt(1 + 1j * omega * t_G)
        * np.tanh(phi * np.sqrt(1 + 1j * omega * t_G))
    )
    return Z


@element(num_params=2, units=["Ohm", "sec"])
def K(p, f):
    """An RC element for use in lin-KK model

    Notes
    -----
    .. math::

        Z = \\frac{R}{1 + j \\omega \\tau_k}

    """
    omega = 2 * np.pi * np.array(f)
    R, tau_k = p[0], p[1]
    Z = R / (1 + 1j * omega * tau_k)
    return Z


@element(num_params=3, units=['Ohm', 'sec', ''])
def Zarc(p, f):
    """ An RQ element rewritten with resistance and
    and time constant as paramenters. Equivalent to a
    Cole-Cole relaxation in dielectrics.

    Notes
    -----
    .. math::

        Z = \\frac{R}{1 + (j \\omega \\tau_k)^\\gamma }

    """
    omega = 2*np.pi*np.array(f)
    R, tau_k, gamma = p[0], p[1], p[2]
    Z = R/(1 + ((1j*omega*tau_k)**gamma))
    return Z


@element(num_params=3, units=["Ohm", "F sec^(gamma - 1)", ""])
def TLMQ(p, f):
    """Simplified transmission-line model as defined in Eq. 11 of [1]

    Notes
    -----
    .. math::

        Z = \\sqrt{R_{ion}Z_{S}} \\coth \\sqrt{\\frac{R_{ion}}{Z_{S}}}


    [1] J. Landesfeind et al.,
    Journal of The Electrochemical Society, 163 (7) A1373-A1387 (2016)
    `doi: 10.1016/10.1149/2.1141607jes
    <http://doi.org/10.1149/2.1141607jes>`_.
    """
    omega = 2 * np.pi * np.array(f)
    Rion, Qs, gamma = p[0], p[1], p[2]
    Zs = 1 / (Qs * (1j * omega) ** gamma)
    Z = np.sqrt(Rion * Zs) / np.tanh(np.sqrt(Rion / Zs))
    return Z


@element(num_params=4, units=["Ohm-m^2", "Ohm-m^2", "", "sec"])
def T(p, f):
    """A macrohomogeneous porous electrode model from Paasch et al. [1]

    Notes
    -----
    .. math::

        Z = A\\frac{\\coth{\\beta}}{\\beta} + B\\frac{1}{\\beta\\sinh{\\beta}}

    where

    .. math::

        A = d\\frac{\\rho_1^2 + \\rho_2^2}{\\rho_1 + \\rho_2} \\quad
        B = d\\frac{2 \\rho_1 \\rho_2}{\\rho_1 + \\rho_2}

    and

    .. math::
        \\beta = (a + j \\omega b)^{1/2} \\quad
        a = \\frac{k d^2}{K} \\quad b = \\frac{d^2}{K}


    [1] G. Paasch, K. Micka, and P. Gersdorf,
    Electrochimica Acta, 38, 2653–2662 (1993)
    `doi: 10.1016/0013-4686(93)85083-B
    <https://doi.org/10.1016/0013-4686(93)85083-B>`_.
    """

    omega = 2 * np.pi * np.array(f)
    A, B, a, b = p[0], p[1], p[2], p[3]
    beta = (a + 1j * omega * b) ** (1 / 2)

    sinh = []
    for x in beta:
        if x < 100:
            sinh.append(np.sinh(x))
        else:
            sinh.append(1e10)

    Z = A / (beta * np.tanh(beta)) + B / (beta * np.array(sinh))
    return Z

@element(num_params=6, units=["Ohm-m^2", "Ohm-m^2", "", "sec","m^2","s"])
def TDP(p, f):
    """A macrohomogeneous porous electrode model from Paasch et al. [1]

    Notes
    -----
    .. math::

        Z = A\\frac{\\coth{\\beta}}{\\beta} + B\\frac{1}{\\beta\\sinh{\\beta}}

    where

    .. math::

        A = d\\frac{\\rho_1^2 + \\rho_2^2}{\\rho_1 + \\rho_2} \\quad
        B = d\\frac{2 \\rho_1 \\rho_2}{\\rho_1 + \\rho_2}

    and

    .. math::
        \\beta = (a + j \\omega b)^{1/2} \\quad
        a = \\frac{k d^2}{K} \\quad b = \\frac{d^2}{K}


    In the common case of low resistivity electrodes, setting B = 0 simplifies
    the system to one term. 
    
    >> Z = \frac{A}{\beta \cdot \tanh(\beta)}

    This is identical to the result of Ji et al. [2] in Eq. 35.

    [1] G. Paasch, K. Micka, and P. Gersdorf,
    Electrochimica Acta, 38, 2653–2662 (1993)
    `doi: 10.1016/0013-4686(93)85083-B
    <https://doi.org/10.1016/0013-4686(93)85083-B>`_.

    [2] Y. Ji and D. T. Schwartz, 
    J. Electrochem. Soc., 170, 123511 (2023)
    `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.
    
    EIS: A macrohomogeneous porous electrode model with planar diffusion 
    Planar

    """
    omega = 2*np.pi*np.array(f)
    A, B, a, b, Aw, taoD = p[0], p[1], p[2],p[3],p[4], p[5]
    Rpore = A
    Rct = (A+B)/a
    Cdl = b/(A+B)

    Zd = Aw / (np.tanh(np.sqrt(1j*omega*taoD)) * np.sqrt(1j*omega*taoD))
    beta = (1j*omega*Cdl*Rpore+Rpore/(Zd+Rct))**(1/2)
    
    sinh = []
    for x in beta:
        if x < 100:
            sinh.append(np.sinh(x))
        else:
            sinh.append(1e10)
    
    Z = A / (beta*np.tanh(beta)) + B / (beta*np.sinh(beta))

    return Z

@element(num_params=6, units=["Ohm-m^2", "Ohm-m^2", "", "sec","m^2","s"])
def TDC(p, f):
    """ 
    Notes
    -----
    .. math::

        Z = A\\frac{\\coth{\\beta}}{\\beta} + B\\frac{1}{\\beta\\sinh{\\beta}}

    where

    .. math::

        A = d\\frac{\\rho_1^2 + \\rho_2^2}{\\rho_1 + \\rho_2} \\quad
        B = d\\frac{2 \\rho_1 \\rho_2}{\\rho_1 + \\rho_2}

    and

    .. math::
        \\beta = (a + j \\omega b)^{1/2} \\quad
        a = \\frac{k d^2}{K} \\quad b = \\frac{d^2}{K}


    In the common case of low resistivity electrodes, setting B = 0 simplifies
    the system to one term. 
    
    >> Z = \frac{A}{\beta \cdot \tanh(\beta)}

    This is identical to the result of Ji et al. [2] in Eq. 35.

    [1] G. Paasch, K. Micka, and P. Gersdorf,
    Electrochimica Acta, 38, 2653–2662 (1993)
    `doi: 10.1016/0013-4686(93)85083-B
    <https://doi.org/10.1016/0013-4686(93)85083-B>`_.

    [2] Y. Ji and D. T. Schwartz, 
    J. Electrochem. Soc., 170, 123511 (2023)
    `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.
    
    EIS: A macrohomogeneous porous electrode model with cylindrical diffusion
    # A=Rpore
    # B=Rct
    # a=Cdl
    # b=Aw
    # c=taoD
    """
    omega = 2*np.pi*np.array(f)
    A, B, a, b, Aw, taoD = p[0], p[1], p[2],p[3],p[4], p[5]
    Rpore = A
    Rct = (A+B)/a
    Cdl = b/(A+B)
    i0 = []
    i1 = []
    sqrt_term = np.sqrt(1j*omega*taoD)
    
    for x in sqrt_term:
        if x < 100:
            i0.append(iv(0,x))
            i1.append(iv(1,x))
        else:
            i0.append(1e20)
            i1.append(1e20)
            
    Zd = Aw*np.array(i0)/((sqrt_term)*np.array(i1))
    beta = (1j*omega*Rpore*Cdl+Rpore/(Zd+Rct))**(1/2)
    
    sinh = []
    for x in beta:
        if x < 100:
            sinh.append(np.sinh(x))
        else:
            sinh.append(1e10)
            
    Z = A / (beta * np.tanh(beta)) + B / (beta * np.array(sinh))
    return Z


@element(num_params=6, units=["Ohm-m^2", "Ohm-m^2", "", "sec","m^2","s"])
def TDS(p, f):
    """ 
    Notes
    -----
    .. math::

        Z = A\\frac{\\coth{\\beta}}{\\beta} + B\\frac{1}{\\beta\\sinh{\\beta}}

    where

    .. math::

        A = d\\frac{\\rho_1^2 + \\rho_2^2}{\\rho_1 + \\rho_2} \\quad
        B = d\\frac{2 \\rho_1 \\rho_2}{\\rho_1 + \\rho_2}

    and

    .. math::
        \\beta = (a + j \\omega b)^{1/2} \\quad
        a = \\frac{k d^2}{K} \\quad b = \\frac{d^2}{K}


    In the common case of low resistivity electrodes, setting B = 0 simplifies
    the system to one term. 
    
    >> Z = \frac{A}{\beta \cdot \tanh(\beta)}

    This is identical to the result of Ji et al. [2] in Eq. 35.

    [1] G. Paasch, K. Micka, and P. Gersdorf,
    Electrochimica Acta, 38, 2653–2662 (1993)
    `doi: 10.1016/0013-4686(93)85083-B
    <https://doi.org/10.1016/0013-4686(93)85083-B>`_.

    [2] Y. Ji and D. T. Schwartz, 
    J. Electrochem. Soc., 170, 123511 (2023)
    `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.
    
    EIS: A macrohomogeneous porous electrode model with spherical diffusion
    # A=Rpore
    # B=Rct
    # a=Cdl
    # b=Aw
    # c=taoD
    """
    
    omega = 2*np.pi*np.array(f)
    A, B, a, b, Aw, taoD = p[0], p[1], p[2],p[3],p[4], p[5]
    _, Rpore, Rct, Cdl = get_pore_params(A,B,a,b)
    
    sqrt_term = np.sqrt(1j*omega*taoD)
    Zd = Aw*np.tanh(sqrt_term)/(sqrt_term-np.tanh(sqrt_term))
    beta = (1j*omega*Rpore*Cdl+Rpore/(Zd+Rct))**(1/2)
    
    sinh = []
    for x in beta:
        if x < 100:
            sinh.append(np.sinh(x))
        else:
            sinh.append(1e10)
    
    Z = A / (beta * np.tanh(beta)) + B / (beta * np.array(sinh))
    return Z


#Duplicates for Notebook Only
@element(num_params=6, units=["Ohm-m^2", "Ohm-m^2", "", "sec","m^2","s"]) #TODO: delete when done
def TDSS(p, f):
    
    """ 
    Notes
    -----
    .. math::

        Z = A\\frac{\\coth{\\beta}}{\\beta} + B\\frac{1}{\\beta\\sinh{\\beta}}

    where

    .. math::

        A = d\\frac{\\rho_1^2 + \\rho_2^2}{\\rho_1 + \\rho_2} \\quad
        B = d\\frac{2 \\rho_1 \\rho_2}{\\rho_1 + \\rho_2}

    and

    .. math::
        \\beta = (a + j \\omega b)^{1/2} \\quad
        a = \\frac{k d^2}{K} \\quad b = \\frac{d^2}{K}


    In the common case of low resistivity electrodes, setting B = 0 simplifies
    the system to one term. 
    
    >> Z = \frac{A}{\beta \cdot \tanh(\beta)}

    This is identical to the result of Ji et al. [2] in Eq. 35.

    [1] G. Paasch, K. Micka, and P. Gersdorf,
    Electrochimica Acta, 38, 2653–2662 (1993)
    `doi: 10.1016/0013-4686(93)85083-B
    <https://doi.org/10.1016/0013-4686(93)85083-B>`_.

    [2] Y. Ji and D. T. Schwartz, 
    J. Electrochem. Soc., 170, 123511 (2023)
    `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.
    
    EIS: A macrohomogeneous porous electrode model with spherical diffusion
    # A=Rpore
    # B=Rct
    # a=Cdl
    # b=Aw
    # c=taoD
    """
    omega = 2*np.pi*np.array(f)
    A, B, a, b, Aw, taoD = p[0], p[1], p[2],p[3],p[4], p[5]
    _, Rpore, Rct, Cdl = get_pore_params2(A,B,a,b)
    sqrt_term = np.sqrt(1j*omega*taoD)
    Zd = Aw*np.tanh(sqrt_term)/(sqrt_term-np.tanh(sqrt_term))
    beta = (1j*omega*Rpore*Cdl+Rpore/(Zd+Rct))**(1/2)
    sinh = []
    for x in beta:
        if x < 100:
            sinh.append(np.sinh(x))
        else:
            sinh.append(1e10)
    
    Z = A / (beta * np.tanh(beta)) + B / (beta * np.array(sinh))
    return Z


def get_pore_params(A,B,a,b): #Analytical Method (more exact)
    #TODO: added chosen functions
    
    R1, R2, Rct, Cdl = symbols('R1, R2, Rct, Cdl')
    eq1 = Eq((R1**2+R2**2) / (R1+R2), A)
    eq2 = Eq((2*R1*R2)/(R1+R2), B)
    eq3 = Eq((R1+R2)/Rct,a)
    eq4 = Eq(Cdl*(R1+R2),b)

    sols = solve([eq1, eq2, eq3, eq4], [R1,R2,Rct,Cdl], real = True)

    # for sol in sols:
    #     R1,R2,Rct,Cdl = sol[0],sol[1],sol[2],sol[3]
    R1,R2,Rct,Cdl = sols[0][0],sols[0][1],sols[0][2],sols[0][3] #TODO: fix this for loop (like this for testing)
    
    return float(R1.evalf()),float(R2.evalf()),float(Rct.evalf()),float(Cdl.evalf())

def get_pore_params2(A,B,a,b): #Analytical Method (more exact)
    #TODO: added chosen functions
    
    R1, R2, Rct, Cdl = symbols('R1, R2, Rct, Cdl')
    eq1 = Eq((R1**2+R2**2) / (R1+R2), A)
    eq2 = Eq((2*R1*R2)/(R1+R2), B)
    eq3 = Eq((R1+R2)/Rct,a)
    eq4 = Eq(Cdl*(R1+R2),b)

    sols = solve([eq1, eq2, eq3, eq4], [R1,R2,Rct,Cdl], real = True)

    # for sol in sols:
    #     R1,R2,Rct,Cdl = sol[0],sol[1],sol[2],sol[3]
    R1,R2,Rct,Cdl = sols[1][0],sols[1][1],sols[1][2],sols[1][3] #TODO: fix this for loop (like this for testing)
    
    return float(R1.evalf()),float(R2.evalf()),float(Rct.evalf()),float(Cdl.evalf())

def get_element_from_name(name):
    excluded_chars = "0123456789_"
    return "".join(char for char in name if char not in excluded_chars)


def typeChecker(p, f, name, length):
    assert isinstance(p, list), \
        "in {}, input must be of type list".format(name)
    for i in p:
        assert isinstance(
            i, (float, int, np.int32, np.float64)
        ), "in {}, value {} in {} is not a number".format(name, i, p)
    for i in f:
        assert isinstance(
            i, (float, int, np.int32, np.float64)
        ), "in {}, value {} in {} is not a number".format(name, i, f)
    assert len(p) == length, "in {}, input list must be length {}".format(
        name, length
    )
    return

# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from armi.nucDirectory import nucDir, nuclideBases
from armi.utils import units
from armi import runLog


def getNDensFromMasses(rho, massFracs, normalize=False):
    """
    Convert density (g/cc) and massFracs vector into a number densities vector (#/bn-cm).

    Parameters
    ----------
    rho : float
        density in (g/cc)
    massFracs : dict
        vector of mass fractions -- normalized to 1 -- keyed by their nuclide
        name

    Returns
    -------
    numberDensities : dict
        vector of number densities (#/bn-cm) keyed by their nuclide name
    """
    if normalize:
        massFracs = normalizeNuclideList(massFracs, normalization=normalize)

    numberDensities = {}
    rho = rho * units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
    for nucName, massFrac in massFracs.items():
        atomicWeight = nuclideBases.byName[nucName].weight
        numberDensities[nucName] = massFrac * rho / atomicWeight
    return numberDensities


def getMassFractions(numberDensities):
    """
    Convert number densities (#/bn-cm) into mass fractions.

    Parameters
    ----------
    numberDensities : dict
        number densities (#/bn-cm) keyed by their nuclide name

    Returns
    -------
    massFracs : dict
        mass fractions -- normalized to 1 -- keyed by their nuclide
        name
    """
    nucMassFracs = {}
    totalWeight = 0.0
    for nucName, numDensity in numberDensities.items():
        weightI = numDensity * nucDir.getAtomicWeight(nucName)
        nucMassFracs[nucName] = weightI  # will be normalized at end
        totalWeight += weightI

    if totalWeight != 0:
        for nucName in numberDensities:
            nucMassFracs[nucName] /= totalWeight
    else:
        for nucName in numberDensities:
            nucMassFracs[nucName] = 0.0

    return nucMassFracs


def calculateMassDensity(numberDensities):
    """
    Calculates the mass density.

    Parameters
    ----------
    numberDensities : dict
        vector of number densities (atom/bn-cm) indexed by nuclides names

    Returns
    -------
    rho : float
        density in (g/cc)
    """
    rho = 0
    for nucName, nDensity in numberDensities.items():
        atomicWeight = nuclideBases.byName[nucName].weight
        rho += nDensity * atomicWeight / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
    return rho


def calculateNumberDensity(nucName, mass, volume):
    """
    Calculates the number density.

    Parameters
    ----------
    mass : float
    volume : volume
    nucName : armi nuclide name -- e.g. 'U235'

    Returns
    -------
    number density : float
        number density (#/bn-cm)

    See Also
    --------
    armi.reactor.blocks.Block.setMass
    """
    A = nucDir.getAtomicWeight(nucName)
    try:
        return units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * mass / (volume * A)
    except ZeroDivisionError:
        if mass == 0 and volume == 0:
            return 0

        raise ValueError(
            "Could not calculate number density with input.\n"
            "mass : {}\nvolume : {}\natomic weight : {}\n".format(mass, volume, A)
        )


def getMassInGrams(nucName, volume, numberDensity=None):
    """
    Gets mass of a nuclide of a known volume and know number density.

    Parameters
    ----------
    nucName : str
        name of nuclide -- e.g. 'U235'
    volume : float
        volume in (cm3)
    numberDensity : float
        number density in (at/bn-cm)

    Returns
    -------
    mass : float
        mass of nuclide (g)
    """
    if not numberDensity:
        return 0.0
    A = nucDir.getAtomicWeight(nucName)
    return numberDensity * volume * A / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM


def formatMaterialCard(
    densities,
    matNum=0,
    minDens=1e-15,
    sigFigs=8,
    mcnp6Compatible=False,
    mcnpLibrary=None,
):
    """
    Formats nuclides and densities into a MCNP material card.

    Parameters
    ----------
    densities : dict
        number densities indexed by nuclideBase

    matNum : int
        mcnp material number

    minDens : float
        minimum density

    sigFigs : int
        significant figures for the material card

    Returns
    -------
    mCard : list
        list of material card strings
    """
    if all(
        isinstance(nuc, (nuclideBases.LumpNuclideBase, nuclideBases.DummyNuclideBase))
        for nuc in densities
    ):
        return []  # no valid nuclides to write
    mCard = ["m{matNum}\n".format(matNum=matNum)]
    for nuc, dens in sorted(densities.items()):
        # skip LFPs and Dummies.
        if isinstance(nuc, (nuclideBases.LumpNuclideBase)):
            runLog.important(
                "The material card returned will ignore LFPs.", single=True
            )
            continue
        elif isinstance(nuc, nuclideBases.DummyNuclideBase):
            runLog.info("Omitting dummy nuclides such as {}".format(nuc), single=True)
            continue
        mcnpNucName = nuc.getMcnpId()
        newEntry = ("      {nucName:5d} {ndens:." + str(sigFigs) + "e}\n").format(
            nucName=int(mcnpNucName), ndens=max(dens, minDens)
        )  # 0 dens is invalid
        mCard.append(newEntry)

    if mcnp6Compatible:
        mCard.append("      nlib={lib}c\n".format(lib=mcnpLibrary))
    return mCard


def filterNuclideList(nuclideVector, nuclides):
    """
    Filter out nuclides not in the nuclide vector.

    Parameters
    ----------
    nuclideVector : dict
        dictionary of values indexed by nuclide identifiers -- e.g. nucNames or nuclideBases

    nuclides : list
        list of nuclide identifiers

    Returns
    -------
    nuclideVector : dict
        dictionary of values indexed by nuclide identifiers -- e.g. nucNames or nuclideBases
    """
    if not isinstance(list(nuclideVector.keys())[0], nuclides[0].__class__):
        raise ValueError(
            "nuclide vector is indexed by {} where as the nuclides list is {}".format(
                nuclideVector.keys()[0].__class__, nuclides[0].__class__
            )
        )

    for nucName in list(nuclideVector.keys()):
        if nucName not in nuclides:
            del nuclideVector[nucName]

    return nuclideVector


def normalizeNuclideList(nuclideVector, normalization=1.0):
    """
    normalize the nuclide vector.

    Parameters
    ----------
    nuclideVector : dict
        dictionary of values -- e.g. floats, ints -- indexed by nuclide identifiers -- e.g. nucNames or nuclideBases

    normalization : float

    Returns
    -------
    nuclideVector : dict
        dictionary of values indexed by nuclide identifiers -- e.g. nucNames or nuclideBases
    """

    normalizationFactor = sum(nuclideVector.values()) / normalization

    for nucName, mFrac in nuclideVector.items():
        nuclideVector[nucName] = mFrac / normalizationFactor

    return nuclideVector


def expandElementalMassFracsToNuclides(massFracs, elements):
    """
    Expand elemental mass fractions to natural nuclides.

    Modifies the input ``massFracs`` to contain nuclides.

    Notes
    -----
    This indirectly updates number densities through mass fractions.

    Parameters
    ----------
    massFracs : dict(str, float)
        dictionary of nuclide or element names with mass fractions.
        Elements will be expanded using natural isotopics.

    elements : iterable of Elements
        element objects to expand (from nuclidBase.element).
    """
    # expand elements
    for element in elements:
        massFrac = massFracs.pop(element.symbol, None)
        if massFrac is None:
            continue

        expandedNucs = expandElementalNuclideMassFracs(element, massFrac)
        massFracs.update(expandedNucs)

        total = sum(expandedNucs.values())
        if massFrac > 0.0 and abs(total - massFrac) / massFrac > 1e-6:
            raise ValueError(
                "Mass fractions not normalized properly {}!".format((total, massFrac))
            )


def expandElementalNuclideMassFracs(element, massFrac):
    """Return a dictionary of nuclide names to natural mass fractions."""
    nucBases = element.getNaturalIsotopics()
    elementalWeightGperMole = sum(nb.weight * nb.abundance for nb in nucBases)
    if not any(nucBases):
        raise ValueError("Cannot expand element {}".format(element))
    expanded = {}
    for nb in nucBases:
        mult = nb.abundance if len(nucBases) > 1 else 1.0
        expanded[nb.name] = massFrac * mult * nb.weight / elementalWeightGperMole
    return expanded


def getChemicals(nuclideInventory):
    """
    Groups the inventories of nuclides by their elements.

    Parameters
    ----------
    nuclideInventory : dict
        nuclide inventories indexed by nuc -- either nucNames or nuclideBases

    Returns
    -------
    chemicals : dict
        inventory of elements indexed by element symbol -- e.g. 'U' or 'PU'
    """
    chemicals = {}
    for nuc, N in nuclideInventory.items():
        nb = nuc if isinstance(nuc, nuclideBases.INuclide) else nuclideBases.byName[nuc]

        if nb.element.symbol in chemicals:
            chemicals[nb.element.symbol] += N
        else:
            chemicals[nb.element.symbol] = N

    return chemicals

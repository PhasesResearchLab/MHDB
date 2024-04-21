import operator
from functools import reduce
from pymatgen.core import Composition
from pymatgen.ext.optimade import OptimadeRester
from pymatgen.util.provenance import StructureNL
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.analysis.phase_diagram import PhaseDiagram

# Create OPTIMADE function to return a data_collection that can be looped calling DFTEntryGenerator
def callOPTIMADE(elements:list, providerNames:list=None, stabilityCriteria:float=0):

    providers = {
        "https://optimade.materialsproject.org":[['_mp_stability', 'gga_gga+u_r2scan', 'energy_above_hull'], ["_mp_stability", "gga_gga+u", "formation_energy_per_atom"]], 
        "http://oqmd.org/optimade/":[['_oqmd_stability'], ['_oqmd_delta_e']], 
        "https://alexandria.icams.rub.de/pbesol/structures":[['_alexandria_hull_distance'],['_alexandria_formation_energy_per_atom']]
    }

    if providerNames != None:
        providers = {key: providers[key] for key in list(providerNames) if key in providers}
    
    all_results = {}
    for provider, criteria in providers.items():
        results = OptimadeRester(provider, timeout=50).get_snls(nelements=len(elements), elements=elements, additional_response_fields=[criteria[0][0],criteria[1][0]])

        # Exclude materials in dict based on a meta-stability criteria
        if results.get(provider):
            results[provider] = {key: value for key, value in results[provider].items() 
                                if reduce(operator.getitem, [value.data['_optimade']] + providers[provider][0]) <= stabilityCriteria} #Implement alternative version using MPDD stability criteria and fecthing the data from OPTIMADE 
        
            all_results = {**all_results, **results[provider]}

    from pymatgen.ext.matproj import MPRester
    mpr = MPRester("YwQWgrlZJzwQ4TOVxHW1Kjh2GIADKI1R")
    pd = PhaseDiagram(mpr.get_entries_in_chemsys(elements))

    data_collection = []
    for materialID, structure in all_results.items():
        if isinstance(structure, StructureNL):
            composition = structure.structure.composition
            analyzer = SpacegroupAnalyzer(structure.structure)
            space_group_number = analyzer.get_space_group_number()
            wyckoffs = analyzer.get_symmetry_dataset()['wyckoffs']

            label_dict = {
                '2a229': 'BCC',
                '4a225': 'FCC',
                '2c194': 'HCP',
                '4a4b225': 'Rocksalt',
                '4a8c225': 'Fluorite',
                '1a1b3c225': 'Perovskite',
                '8a16d32e227': 'Spinel'
            }

            structure_label = ''.join(f"{wyckoffs.count(element)}{element}" for element in set(wyckoffs)) + str(space_group_number)
            structure_label = label_dict.get(structure_label, structure_label)

            formationReaction = str(pd.get_element_profile('H', Composition(composition.reduced_formula), comp_tol=1e-05)[-2]['reaction']) # Need to account for missing reactants in SSUB. In this case should loop until [-1]['reaction'] 
    
            for provider in providers.keys():
                try: 
                    structure_dict = structure.as_dict()
                    energy_above_hull = reduce(operator.getitem, ["about", "_optimade"] + providers[provider][0], structure_dict)
                    formation_energy_per_atom = reduce(operator.getitem, ["about", "_optimade"] + providers[provider][1], structure_dict)
                except:
                    pass

            data_collection.append({
                'parentDatabase': structure.as_dict()["about"]["history"][0]["name"].upper(),
                'parentDatabaseID': materialID,
                'parentDatabaseURL': materialID,
                'reducedFormula': composition.formula,
                'totalAtoms': Composition(composition.reduced_formula).num_atoms,
                'elements': elements,
                'structureLabel': structure_label,
                'formationReaction': formationReaction,
                'formationEnthalpy': formation_energy_per_atom,
                'energyAboveHull': energy_above_hull,
                'structure': structure.as_dict()
            })

    return data_collection
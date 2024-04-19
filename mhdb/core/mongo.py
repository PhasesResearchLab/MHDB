from mhdb.core import parseTDB
from pycalphad import Database, calculate
from pymatgen.core import Composition
import datetime, re
from pprint import pprint

def updateEntry(entry:dict, client_string:str, db:str, col:str):
    import dns.resolver
    dns.resolver.default_resolver=dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers=['8.8.8.8']
    
    from pymongo import MongoClient
    client = MongoClient(client_string)
    database = client[db] 
    collection = database[col]
    
    if collection.find_one({'metadata.parentDatabaseURL': entry['metadata']['parentDatabaseURL'], 'material.phaseModel': entry['material']['phaseModel']}) is None:
        entry['metadata']['created'] = datetime.datetime.now()
        collection.insert_one(entry)
    
    else:
        entry['metadata']['lastModified'] = datetime.datetime.now()
        match_query = {'material.phaseModel': entry['material']['phaseModel'], 'material.phaseLabel': entry['material']['phaseLabel'], 'material.endmembers': entry['material']['endmembers']}
        update_query = {'$set': {**{k: entry[k] for k in entry if k != 'metadata'}, 'metadata.lastModified': entry['metadata']['lastModified']}}
        collection.update_one(match_query, update_query)
    
    return entry

def TDBEntryGenerator(data:dict, client_string:str, db:str, col:str):
    
    parentDatabaseID = data["phases"][0].split()[1]
    
    metadata = {
        'name': 'TDBGenerated',
        'comment': f'Automated generated based on the {data["references"]} database.',
        'affiliation': 'MHDB',
        'parentDatabase': data["references"][0],
        'parentDatabaseID': parentDatabaseID,
        'parentDatabaseURL': "None" if "github" not in client_string else "hash"
    }
    
    elements = [element.split()[1] for element in data["elements"]]
    species = list(filter(None, data["phases"][0].split('!')[1].split()[2].split(':')))
    sublatices = [data["phases"][0].split('!')[0].rsplit(' ', len(species)+1)[-(sublatice+2)] for sublatice in range(len(species))][::-1]
    phaseModel = ''.join([f'({''.join([i.capitalize() if i.isalpha() else i for i in re.findall(r'[A-Za-z]+|\d+', x)])}){y}' for x, y in zip(species, sublatices)]) #Capitalize only first letter of species
    try:
        formula = Composition(re.sub(r'\(\)\d+(\.\d+)?', '', re.sub(r'[+-]\d+', '', phaseModel).replace('VA',''))).reduced_formula #Accounts for vacancies and charged species
    except:
        formula = parentDatabaseID.split('_')[0]
    
    material = {
        'system': '-'.join(elements),
        'endmembers': '-'.join([formula]), #Still need to separate endmembers in case of solid solutions
        'phaseLabel': parentDatabaseID.split('_')[-1].split(':')[-1],
        'phaseModel': phaseModel
    }

    dbf = Database(parseTDB.one2tdb(data))

    try:
        SER = round(calculate(dbf, elements + ['VA'], parentDatabaseID.split(':')[0], P=101325, T=298.15).GM.values[0][0][0][0], 4)
    except:
        SER = None
    
    material.update({'SER': SER})
       
    entry = {"metadata": metadata, "material": material, "tdb": data}
    
    return updateEntry(entry, client_string, db, col)

def DFTEntryGenerator(data:dict, client_string:str, db:str, col:str):

    from pymongo import MongoClient, ASCENDING
    client = MongoClient(client_string)

    metadata = {
        'name': 'DFTGenerated', 
        'comment': f'Automated generated based on the {data['parentDatabase']} database.',
        'affiliation': 'MHDB',
        'parentDatabase': data['parentDatabase'], 
        'parentDatabaseID': data['parentDatabaseID'],
        'parentDatabaseURL': data['parentDatabaseURL']
    }
    
    elements = data['elements']
    endmembers = [data['reducedFormula']]
    formationReaction = data['formationReaction']

    material = {
        'system': '-'.join(elements),
        'endmembers': '-'.join(endmembers), #Still need to separate endmembers in case of solid solutions
        'phaseLabel': data['structureLabel'],
        'phaseModel': f'({endmembers[0]})1.0'
    }
    
    dft = {
        'decomposesTo': formationReaction,
        'formationEnthalpy': data['formationEnthalpy'],
        'formationEntropy': data['formationEntropy']*data['totalAtoms'] if 'formationEntropy' in data.keys() else 0,
        'mixingEnthalpy': data['mixingEnthalpy']*data['totalAtoms'] if 'mixingEnthalpy' in data.keys() else 0
    }

    decomposesTo = {}
    for constituent in formationReaction.split('->')[1].split('+'):
        # Use a regular expression to separate the coefficient from the compound name
        match = re.match(r'(\d*\.?\d*)\s*(\w+)', Composition(constituent).formula.replace(" ",""))
        if match:
            # If no coefficient is found, assume it to be 1
            coefficient = float(match.group(1)) if match.group(1) else 1.0
            compound_name = match.group(2)
            decomposesTo[compound_name] = coefficient

    tdb_elements = []
    tdb_parameters = []
    tdb_symbols = []
    tdb_references = []
    for constituent in decomposesTo.keys():
        result = client['MHDB']['MSUB'].find({"material.endmembers": constituent}).sort("material.SER", ASCENDING).limit(1)
        for key, value in result[0]['tdb'].items(): # Need to account when len(result) == 0
            if key == 'elements':
                tdb_elements += value if value not in tdb_elements else []
            elif key == 'symbols':
                tdb_symbols += value if value not in tdb_symbols else []
            elif key == 'references':
                tdb_references += value if value not in tdb_references else []
            elif key == 'parameters':
                for contribution in value:
                    contr_name = 'FSER' + contribution.split(' ')[1].split('(')[0] + constituent.upper()
                    contr_func = contribution.split(' N ')[0].split(' ',2)[2] + ' N !'
                    tdb_parameters.append('+' + contr_name)
                    tdb_symbols.append(f"FUNCTION {contr_name} {contr_func}")

    phase_name = f'{material['endmembers'].upper()}_{material['phaseLabel'].upper()}'

    phase_model = {}
    matches = re.findall(r'\((.*?)\)(\d*\.?\d*)', material['phaseModel'])
    for match in matches:
        phase_model[match[0]] = float(match[1])

    for species in map(lambda x: x.upper(), phase_model.keys()):
        tdb_species = [f"SPECIES {specie} {specie}!" for specie in species.split(',')] # Update for multiple sublattices
        tdb_species = list(set(tdb_species))

    tdb = {
        "elements": tdb_elements,
        "species": tdb_species,
        "phases": [f"PHASE {phase_name} % {len(phase_model)} {' '.join(map(str, phase_model.values()))} ! CONSTITUENT {phase_name} :{':'.join(map(lambda x: x.upper(), phase_model.keys()))}: !"],
        "parameters": [f"PARAMETER G({phase_name},{':'.join(map(lambda x: x.upper(), phase_model.keys()))};0) 298.15 {''.join(tdb_parameters)} {dft['formationEnthalpy']*data['totalAtoms']*96.48792534459*1000}-T*{dft['formationEntropy']*data['totalAtoms']*96.48792534459};  6000 N !"], # will need to separate in case of solid solutions
        "symbols": tdb_symbols,
        "references": tdb_references
    }

    pprint(tdb)
    dbf = Database(parseTDB.one2tdb(tdb))

    try:
        SER = round(calculate(dbf, elements + ['VA'], phase_name, P=101325, T=298.15).GM.values[0][0][0][0], 4)
    except:
        SER = None
    
    material.update({'SER': SER})

    entry = {"metadata": metadata, "material": material, "dft": dft, "tdb": tdb}

    # return from_string
    return updateEntry(entry, client_string, db, col)

# Alternative method for decomposeTo:
# decomp = pd.get_decomposition(comp)
# Print the decomposition products and their amounts
# for entry, amount in decomp.items():
#    print(f"{entry.composition.reduced_formula}: {amount}")
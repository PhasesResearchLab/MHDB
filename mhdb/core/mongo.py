import dns.resolver
dns.resolver.default_resolver=dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers=['8.8.8.8']

from pymongo import MongoClient

client_string='mongodb+srv://rdamaral:GBmJrZ8XIsCCcWWQ@plr-cluster.ls9prsp.mongodb.net/'
client = MongoClient(client_string)

db = client['MHDB'] 
collection = db['curated']

import datetime

def updateEntry(entry:dict, collection):
    collection = db[collection]
    
    if collection.find_one({'material.phaseModel': entry['material']['phaseModel'], 'material.phaseLabel': entry['material']['phaseLabel'], 'material.endmembers': entry['material']['endmembers']}) is None:
        entry['metadata']['created'] = datetime.datetime.now()
        collection.insert_one(entry)
        return entry
    
    else:
        entry['metadata']['lastModified'] = datetime.datetime.now()
        match_query = {'material.phaseModel': entry['material']['phaseModel'], 'material.phaseLabel': entry['material']['phaseLabel'], 'material.endmembers': entry['material']['endmembers']}
        update_query = {'$set': {**{k: entry[k] for k in entry if k != 'metadata'}, 'metadata.lastModified': entry['metadata']['lastModified']}}
        collection.update_one(match_query, update_query)
        return entry

from pymatgen.core import Composition

def TDBEntryGenerator(data:dict, collection:str='curated'):
    
    metadata = {
        'name': 'TDBGenerated',
        'comment': f'Automated generated based on the {data["references"]} database.',
        'affiliation': 'MHDB',
        'parentDatabase': data["references"],
        'parentDatabaseID': data["phases"][0].split()[1]
    }
    
    elements = [element.split()[1] for element in data["elements"]]
    species = list(filter(None, data["phases"][0].split('!')[1].split()[2].split(':')))
    sublatices = [data["phases"][0].split('!')[0].rsplit(' ', len(species)+1)[-(sublatice+2)] for sublatice in range(len(species))][::-1]
    phaseModel = ''.join([f'({''.join([i.capitalize() if i.isalpha() else i for i in re.findall(r'[A-Za-z]+|\d+', x)])}){y}' for x, y in zip(species, sublatices)]) #Capitalize only first letter of species
    try:
        formula = Composition(re.sub(r'\(\)\d+(\.\d+)?', '', re.sub(r'[+-]\d+', '', phaseModel).replace('VA',''))).reduced_formula #Accounts for vacancies and charged species
    except:
        formula = data["phases"][0].split()[1].split('_')[0]
    
    material = {
        'system': '-'.join(elements),
        'endmembers': '-'.join([formula]), #Still need to separate endmembers in case of solid solutions
        'phaseLabel': data["phases"][0].split()[1].split('_')[-1].split(':')[-1],
        'phaseModel': phaseModel,
        'SER': phaseModel
    }
    
    entry = {"metadata": metadata, "material": material, "tdb": data}
    
    # Check if an entry already exists and update collection:
    return updateEntry(entry, collection)


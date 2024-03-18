import dns.resolver
dns.resolver.default_resolver=dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers=['8.8.8.8']

import re
import json
from pymongo import MongoClient

# FUNCTION FROM database.py
def one2many(data:list):
    data_collection = []
    cache = []

    for k, parameter in enumerate(data['parameters']):
        phase_species = re.search(r'PARAMETER [A-Z]+\(([^;]+);', parameter).group(1)
        if phase_species in cache:
            continue
        
        # Get parameter and secondary parameters
        i = len(data_collection)
        data_collection.append({key: [] for key in data.keys()})
        data_collection[i]['parameters'].append(parameter)
        cache.append(phase_species)

        for j, secondary_parameter in enumerate(data['parameters']):
            if k != j and phase_species == re.search(r'PARAMETER [A-Z]+\(([^;]+);', secondary_parameter).group(1):
                data_collection[i]['parameters'].append(secondary_parameter)
        
        # Get phase > Update constituents
        for phase in data['phases']:
            if phase_species.split(',')[0] == phase.split()[1].split(':')[0]:
                data_collection[i]['phases'].append(f"{phase.split('!')[0]}! CONSTITUENT {phase_species.split(',')[0]} :{phase_species.split(',')[1]}: !{phase.split('!')[2] + '!' if phase.split('!')[2] else ''}")

        # Get species > Get elements
        phase_elements = []
        for phase_specie in phase_species.split(',')[1].split(':'):
            for specie in data['species']:
                if phase_specie == specie.split()[1]:
                    data_collection[i]['species'].append(specie)
            
            for phase_element in [part for part in re.split(r'\d+', phase_specie) if part]:
                if phase_element not in phase_elements:
                    phase_elements.append(phase_element)
                    for element in data['elements']:
                        if phase_element == element.split()[1]:
                            data_collection[i]['elements'].append(element)

        # Get symbols called in parameters
        for phase_parameter in data_collection[i]['parameters']:
            for phase_symbol in re.findall(r'[-+ ](\w+)(?=#)', phase_parameter):  
                for symbol in data['symbols']:
                    if phase_symbol == symbol.split()[1]:
                        data_collection[i]['symbols'].append(symbol)

        # Get symbols called in functions (recursively)
        j = 0
        while j < len(data_collection[i]['symbols']):
            phase_symbol = data_collection[i]['symbols'][j]
            for phase_secondary_symbol in re.findall(r'[-+ ](\w+)(?=#)', phase_symbol):
                for secondary_symbol in data['symbols']:
                    if phase_secondary_symbol == secondary_symbol.split()[1]:
                        data_collection[i]['symbols'].append(secondary_symbol)
            j += 1

    return data_collection

import datetime

def updateEntry(entry:dict, collection):
    collection = db[collection]
    
    if collection.find_one({'material.phaseModel': entry['material']['phaseModel'], 'material.phaseLabel': entry['material']['phaseLabel'], 'material.endmembers': entry['material']['endmembers']}) is None:
        entry['metadata']['created'] = datetime.datetime.now()
        collection.insert_one(entry)
        return entry
    
    else:
        entry['metadata']['lastModified'] = datetime.datetime.now()
        collection.update_one({'material.phaseModel': entry['material']['phaseModel'], 'material.phaseLabel': entry['material']['phaseLabel'], 'material.endmembers': entry['material']['endmembers']}, 
                                      {'$set': {'metadata.lastModified': entry['metadata']['lastModified'], 'material': entry['material'], 'dft': entry['dft'], 'tdb': entry['tdb']}})
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

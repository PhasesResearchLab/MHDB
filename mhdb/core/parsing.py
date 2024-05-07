from pycalphad.io.database import Database
from pprint import pprint
import re, json, os, datetime

def many2tdb(elements, data_collection):
    data = many2one(elements, data_collection)
    data = one2tdb(data)
    return data

def tdb2one(file_path:str):
    fd = open(file_path if '.tdb' in file_path.lower() else file_path + '.tdb', 'r')

    content = fd.read()
    lines = content.upper().replace('\t', ' ').strip()
    # Split the string by newlines
    splitlines = lines.split('\n')
    # Remove extra whitespace inside line
    splitlines = [' '.join(k.split()) for k in splitlines]
    # Remove comments
    splitlines = [k.strip().split('$', 1)[0] for k in splitlines]
    # Remove everything after command delimiter, but keep the delimiter so we can split later
    splitlines = [k.split('!')[0] + ('!' if len(k.split('!')) > 1 else '') for k in splitlines]
    # Combine everything back together
    lines = ' '.join(splitlines)
    # Now split by the command delimeter
    commands = lines.split('!')

    # Define the categories for easy lookup
    categories = {
        'ELEMENT': [],
        'SPECIES': [],
        'FUNCTION': [],
        'TYPE_DEFINITION': [],
        'PHASE': [],
        'PARAMETER': []
    }

    # Loop over each command
    for command in commands:
        # Remove leading whitespace and split the command into words
        command = re.sub(r'^\s+', '', command) + '!'
        words = command.split()

        # If the command is not empty and the category is one of the ones we're interested in
        if words and words[0] in categories:
            # Add the command to the appropriate list
            if 'SEQ' in command:
                continue
            categories[words[0]].append(command)

    # Create a dictionary from the categories
    data = {
        'elements': categories['ELEMENT'],
        'species': categories['SPECIES'],
        'phases': categories['PHASE'],
        'phase_descriptions': categories['TYPE_DEFINITION'],
        'parameters': categories['PARAMETER'],
        'symbols': categories['FUNCTION']
    }

    # phase_names = [re.search(r'PHASE (\w+)', phase).group(1) for phase in data['phases']]
    phase_names = {phase.split()[1].split(':')[0]: phase.split()[3] for phase in data['phases']}
    phase_species = {phase: [[] for _ in range(int(phase_names[phase]))] for phase in phase_names.keys()}
    for phase_name in phase_names.keys():
        for parameter in data['parameters']:
            if phase_name in parameter:
                species = re.search(r'PARAMETER [A-Z]\(' + phase_name + r',\s*([^;]+)', parameter)
                if species:
                    [phase_species[phase_name][sublattice].append(specie) for sublattice, specie in enumerate(species.group(1).replace(' ', '').split(':'))]
        for i, phase in enumerate(data['phases']):
            if phase_name == phase.split()[1].split(':')[0]:
                if phase_name:
                    data['phases'][i] = phase + f' CONSTITUENT {phase_name} :{":".join([','.join(set(",".join(sublattice).split(','))) for sublattice in phase_species[phase_name]])}: !'

    for phase_description in data['phase_descriptions']:
        for j, phase in enumerate(data['phases']):
            if phase_description.split()[4] == phase.split()[1].split(':')[0]:
                data['phases'][j] = phase + f' {phase_description}'

    del data['phase_descriptions']

    def get_username():
        try:
            return os.getlogin()
        except:
            return os.getenv('GITHUB_USER')
    
    # Define the patterns and default values
    patterns = [r'\$ DATABASE_TITLE:(.*?)\n', r'\$ DATABASE_AUTHOR:(.*?)\n', r'\$ DATABASE_YEAR:(.*?)\n', r'\$ DATABASE_DOI:(.*?)\n']
    default_values = [os.path.basename(fd.name), get_username(), datetime.datetime.now().year, '']

    # Initialize the reference_content
    reference_content = ['', '', '', '']

    # Loop over each pattern and default value
    for i, (pattern, default_value) in enumerate(zip(patterns, default_values)):
        # Try to extract the content
        try:
            match = re.search(pattern, content)
            if match.group(1).strip() != '':
                reference_content[i] = match.group(1).strip()
            else:
                raise Exception("Match group is empty")
            
        except:
            try:
                match = re.search(pattern, os.getenv('ISSUE_BODY'))
                if match.group(1).strip() != '':
                    reference_content[i] = match.group(1).strip()
                else:
                    raise Exception("Match group is empty")
                
            except:
                reference_content[i] = default_value

    # Assign the reference_content to title_content, doi_content, author_content, and year_content
    title_content, doi_content = f'{reference_content[0]} | {reference_content[1]} | {reference_content[2]}', reference_content[3]

    data['references'] = [f'{title_content} | {doi_content}' if doi_content != '' else title_content]

    return data

def one2many(data:list):
    data_collection = []
    cache = []

    for k, parameter in enumerate(data['parameters']):
        phase_species = re.search(r'PARAMETER [A-Z0-9]+\(([^;]+);', parameter).group(1).replace(' ','')
        if phase_species in cache:
            continue
        
        # Get parameter and higher order parameters
        i = len(data_collection)
        data_collection.append({key: [] for key in data.keys()})
        data_collection[i]['parameters'].append(parameter)
        cache.append(phase_species)

        for j, secondary_parameter in enumerate(data['parameters']):
            if k != j and phase_species == re.search(r'PARAMETER [A-Z0-9]+\(([^;]+);', secondary_parameter).group(1):
                data_collection[i]['parameters'].append(secondary_parameter)
        
        # Get phase > Update constituents
        for phase in data['phases']:
            if phase_species.split(',')[0] == phase.split()[1].split(':')[0]:
                data_collection[i]['phases'].append(f"{phase.split('!')[0]}! CONSTITUENT {phase_species.split(',')[0]} :{re.split(r'[+-]', phase_species.split(',', 1)[1])[0]}: !{phase.split('!', 2)[2] if phase.split('!')[2] else ''}")

        # Get species > Get elements
        phase_elements = []
        for phase_specie in phase_species.split(',', 1)[1].replace(':', ',').split(','):
            for specie in data['species']:
                if phase_specie == specie.split()[1]:
                    data_collection[i]['species'].append(specie)
                    for phase_element in [part for part in re.split(r'\d+', specie.split()[2]) if part]:
                        if phase_element not in phase_elements:
                            phase_elements.append(element)
                            for element in data['elements']:
                                if phase_element == element.split()[1]:
                                    data_collection[i]['elements'].append(element)
            
            for phase_element in [part for part in re.split(r'\d+', phase_specie) if part]:
                if phase_element not in phase_elements:
                    phase_elements.append(phase_element)
                    for element in data['elements']:
                        if re.split(r'[+-]', phase_element)[0] == element.split()[1]:
                            data_collection[i]['elements'].append(element)

        # Get symbols called in parameters
        for phase_parameter in data_collection[i]['parameters']:
            for phase_symbol in re.findall(r'\b\w{3,}_?\w*\b', phase_parameter):  
                for symbol in data['symbols']:
                    if phase_symbol == symbol.split()[1]:
                        data_collection[i]['symbols'].append(symbol) if symbol not in data_collection[i]['symbols'] else None

        # Get symbols called in functions (recursively)
        j = 0
        while j < len(data_collection[i]['symbols']):
            phase_symbol = data_collection[i]['symbols'][j]
            phase_symbol = ' '.join(phase_symbol.split(' ')[3:-3])
            for phase_secondary_symbol in re.findall(r'(?!EXP)(?=[0-9]*?[A-Z_]+)(?![0-9]+E)([A-Z0-9_]{3,})', phase_symbol):
                for secondary_symbol in data['symbols']:
                    if phase_secondary_symbol == secondary_symbol.split()[1]:
                        data_collection[i]['symbols'].append(secondary_symbol) if secondary_symbol not in data_collection[i]['symbols'] else None
            j += 1
        
        # Get references
        data_collection[i]['references'] = data['references']

    return data_collection

def many2one(elements:list,data_collection:list):

    TDB = {key: [] for key in data_collection[0].keys()}

    # Collect entries according to the elements
    for tdb in data_collection:
        elements_tdb = [line.split()[1] for line in tdb['elements'] if line.split()[1] not in ['VA', '/-']]
        if set(elements_tdb).issubset(set(list(map(str.upper, elements)))):
            TDB['elements'] += tdb['elements']
            TDB['species'] += tdb['species']
            TDB['phases'] += tdb['phases']
            TDB['parameters'] += tdb['parameters']
            TDB['symbols'] += tdb['symbols']
            TDB['references'] += tdb['references']
        
    # Merge entries with the same phase model
    for key, value in TDB.items():
        TDB[key] = list(set(TDB[key]))
        if key == 'phases':
            phase_specie = [[re.search('PHASE (.*?!)', entry).group(1) + entry.split('!', 2)[2], 
                             list(filter(None,entry.split('!')[1].split()[2].split(':')))] for entry in value]
            grouped_data = {}
            for phase, species in phase_specie:
                if phase not in grouped_data:
                    grouped_data[phase] = []
                grouped_data[phase].append(species)
            
            for phase, species in grouped_data.items():
                grouped_data[phase] = [[species[sublattice][specie] for sublattice in range(len(species)) if species[sublattice][specie] != '*'] for specie in range(len(species[0]))]
                grouped_data[phase] = ':'.join([','.join(set(','.join(group).split(','))) for group in grouped_data[phase]])
            
            TDB[key] = [f'PHASE {phase.split('!')[0]}! CONSTITUENT {phase.split()[0].split(':')[0]} :{grouped_data[phase]}: !{phase.split('!', 1)[1] if phase.split('!')[1] else ''}' for phase in grouped_data.keys()]

    return TDB

def one2tdb(data:list):
    from_string = f'''\
{"" if any('ELECTRON_GAS' in element for element in data['elements']) else "ELEMENT /- ELECTRON_GAS 0.0000E+00 0.0000E+00 0.0000E+00!\n"}\
{"" if any('VACUUM' in element for element in data['elements']) else "ELEMENT VA VACUUM 0.0000E+00 0.0000E+00 0.0000E+00!\n"}\
{'\n'.join(data['elements'])}

{'\n'.join(data['species'])}

{'\n'.join(data['symbols'])}

TYPE_DEFINITION % SEQ *!
DEFINE_SYSTEM_DEFAULT ELEMENT 2 !
DEFAULT_COMMAND DEF_SYS_ELEMENT VA /- !

{'\n'.join(data['phases']).replace("! CONSTITUENT", "!\n CONSTITUENT").replace("! TYPE_DEFINITION", "!\n TYPE_DEFINITION")}

{'\n'.join(data['parameters'])}
    '''
    return from_string

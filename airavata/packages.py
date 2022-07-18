from pdb import set_trace as st

from collections.abc import MutableMapping
from copy import deepcopy
from .yaml_manager import ReadYaml


class Packages(ReadYaml):
    """Manage the packages section in stack.yaml"""

    def __init__(self, platform_file, stack_file):
        """Declare class structs"""

        # yaml files
        self.stack_file = stack_file
        self.platform_file = platform_file
        # data
        self.data = {}
        self.stack = {}
        self.specs = []
        # not used
        # self.filtered_stack = {}   # acctually not used
        # self.flat_stack = {}       # acctually not used
        # self._cursor = []          # acctually not used
        # for jinja parsing
        self.pkg_defs = {}
        self.pkgs_yaml = {}
        # options & replacements
        self.options = {}
        self.replacements = {}
        self.pe = {}

    def __call__(self, section):
        """Populate class structs"""

        # Reads stack.yaml into self.data
        self.read(self.stack_file)

        # Groups entries whose section = <section> in self.stack
        self.stack = self.group_sections(deepcopy(self.data), section)

        # Execute replacements (common:variables)
        self.replace_tokens = self.read_replacements(self.platform_file)
        for key, value in self.replace_tokens.items():
            self.do_replace(self.stack, '<' + str(key) + '>', str(value))

        # Read selections
        self.options = self.read_options()

        # Set up dictionaries for later parsing
        for list_name, list_pkgs in self.stack.items():
            self.pkg_defs[list_name] = []
            for pkg in list_pkgs['packages']:
                if isinstance(pkg, str):
                    self.pkg_defs[list_name].append(pkg)
                if isinstance(pkg, dict):
                    spec = self.spec_from_def(pkg)
                    self.pkg_defs[list_name].append(spec)

        self.create_pe_dict()

    def create_pe_dict(self):
        """Create dictionary for parsing jinja template with the package list
        name, the compilers it should use and any dependencies."""

        for pkg_list in self.stack.keys():
            self.pe[pkg_list] = { 'pe': self.stack[pkg_list]['pe'] }
            if 'dependencies' in self.stack[pkg_list]:
                self.pe[pkg_list]['dependencies'] = self.stack[pkg_list]['dependencies']

    def spec_from_def(self, pkg_def):
        """Return spec from definition schema found in stack.yaml

        The spec goes to spack.yaml: this method creates a string for
        the package spec and add this spec (string) to self.defs dict.
        This is the dict that later will be used to parse the template."""

        pkg_name = list(pkg_def.keys())[0]
        spec = [pkg_name]
        settings = pkg_def.get(pkg_name)
        # Process variants
        if 'variants' in settings:
            spec.append(settings.get('variants'))
        # Process spec options
        selected_specs = self.spec_select(self.options, settings)
        if selected_specs:
            spec.append(selected_specs)
        # Process dependencies
        if 'dependencies' in settings:
            for d in settings.get('dependencies'):
                spec.append('^' + d.strip())

        return(' '.join(spec).strip())

    def read_options(self, platform_file = None):
        """Return dict of keys to be replaced in stack file"""

        if not platform_file:
            platform_file = self.platform_file
        common = ReadYaml()
        common.read(platform_file)
        return(common.data['common']['filters'])

    def spec_select(self, options, settings):
        """Return string of selected specs"""

        selection = []
        for opt in options.keys():
            if opt in settings:
                if settings.get(opt).get(options.get(opt)) is None:
                    print(f'Found {opt}:{options.get(opt)} selector but no matching'
                    f' {options.get(opt)} option in stack.yaml')
                    print(f'Exiting...')
                    exit(1)
                selection.append(settings.get(opt).get(options.get(opt)))
        return(' '.join(selection))

    def add_to_packages_yaml(self, pkg_name, selected, options, default_pkg):
        """Add previous selected options (in any) to the default section.
        This prevents the user from having to choose the specs twice."""

        selected_specs = self.spec_select(options, default_pkg)

        # VERY BUGGY INSTRUCTION !!!
        default_pkg['variants'] = ' '.join([default_pkg['variants'], selected, selected_specs])

        for opt in options.keys():
            if opt in default_pkg:
                default_pkg.pop(opt)

        return({pkg_name: default_pkg})

    def create_definitions(self):
        """Create definitions dict for template"""

        for k,v in self.stack.items():
            pkg_list = []
            for pkg in v['packages']:
                pkg_list.append(pkg)
            st()
            self.defs[k] = v['packages'][0]

    def flatten_dict(self, d: MutableMapping, parent_key: str = '', sep: str = '_'):
        """Returns a flat dict

        Return a 1-depth dict (flat) whose elements are formed by composing
        the nested dicts nodes using the separator sep.
        {'a':1, 'b':{'c':2}} -> {'a':1, 'b_c':2}
        origin: freecodecamp.org"""

        return dict(self._flatten_dict_gen(d, parent_key, sep))

    def group_sections(self, dic, section):
        """Returns dictionary composed of common sections

        In the stack.yaml file there can be to different key that both are
        related to packages or to PE. This function will group all section
        which has section value in section key"""

        tmp = {}
        for key in dic:
            if dic[key]['metadata']['section'] == section:
                dic[key].pop('metadata')
                tmp[key] = dic[key]
        return(tmp)

    def _flatten_dict_gen(self, d, parent_key, sep):
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, MutableMapping):
                yield from self.flatten_dict(v, new_key, sep=sep).items()
            else:
                yield new_key, v

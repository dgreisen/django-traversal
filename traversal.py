import yaml as YAML
import re
from django.http import Http404
from collections import OrderedDict
import types
from django.utils import six
from __future__ import absolute_import, division, print_function, unicode_literals

from AppRing import apps as all_apps, models as all_models

splatRe = re.compile(r'^\<(.*)\>$')

def is_string_match(self, path_part):
    return {} if path_part == self.path else None

def is_regex_match(self, path_part):
    match = self.regex.match(path_part)
    return match.groupdict() if match else None

def is_splat_match(self, path_part):
    return {self.variables[0]: path_part}


class ModelContainer(object):
    """
    an object for containing models/resultsets created during traversal.
    """
    def __init__(self, variables=None):
        self.fns = {}
        self.stored_values = {}
        self.variables = variables if variables is not None else VariableContainer()

    def __setitem__(self, key, value):
        if key in self.fns:
            raise TypeError("model exists; cannot be overwritten")
        self.fns[key] = value
        self._current = key

    def __getitem__(self, key):
        if key not in self.stored_values:
            self.stored_values[key] = self.fns[key](all_models, self.variables, self)
        return self.stored_values[key]

    def _get_current(self):
        return self[self._current]
    current = property(_get_current)

    def db_refresh(self, key):
        """
        whatever queryset or model was at key, get it anew from the db.
        """
        self.stored_values[key] = self.fns[key]()
        return self[key]


class VariableContainer(dict):
    """
    an object for containing variables created during traversal.
    """
    def __setitem__(self, key, value):
        if key in self:
            raise TypeError("variable exists; cannot be overwritten")
        super(VariableContainer, self).__setitem__(key, value)
        self._current = [key]

    def update(self, d):
        """
        update self with the dict d, and ensure current points to all keys in d
        """
        for k, v in d.items():
            self[k] = v

        self._current = d.keys()

    def _get_current(self):
        return {k: v for k, v in self.items() if k in self._current}
    current = property(_get_current)

def parse_methods(config):
    out = {"views": {}}
    for k, v in config.items():
        # if all upper case, then it is a method
        if k.upper() == k:
            v = get_function(v) # since it is a method, we need to convert the string to a view object.
            ks = k.split(',')   # split into methods, and add to views dict
            for k in ks:
                out["views"][k.strip()] = v
        else:
            out[k] = v
    return out

class PathTree(object):
    def __init__(self, yaml=None, path=None):
        if path:
            with open(path, 'r') as f:
                yaml = f.read()
        if yaml is None:
            raise BaseException("yaml string or path string to yaml file is required")
        self.conf = YAML.load(yaml)

        self.root = PathNode(**self.conf)

    def traverse(self, request, *args, **kwargs):
        """
        traverse the PathTree, then return the result of calling the destination view,
        passing the variables and models accumulated during traversal
        """
        path = request.path.rstrip('/').split('/')
        view, variables, models = self.root.traverse(request, path, VariableContainer(), ModelContainer(), *args, **kwargs)
        kwargs.update({"variables": variables, "models": models})
        return view(request, *args, **kwargs)

    def test_traverse(self, request, *args, **kwargs):
        """
        traverse the PathTree, just as in traverse, but instead of getting the result the traverse,
        return a tuple of the view, accumulated variables and accumulated models. Useful for unittesting.
        """
        path = request.path.rstrip('/').split('/')
        return self.root.traverse(request, path, VariableContainer(), ModelContainer(), *args, **kwargs)

def get_function(path):
    """
    get a function defined by path from the apps object.
    """
    ns = {"all_apps": all_apps}
    six.exec_('a=' + path, ns)
    return ns['a']



class PathNode(object):
    def __init__(self, path="", parent=None, regex=False, name=None, model=None, children=[], **config):
        self.path = path
        self.parent = parent
        self.regex = regex

        # create the matching function
        self._create_matcher()

        # set name
        self.name = name or (self.variables[0] if len(self.variables) == 1 else self.path)

        # create views
        self.views = parse_methods(config)['views']

        # create model function
        if model:
            self.model = self._generate_model_generator(model)

        # create children and index
        self.children = [PathNode(parent=self, **child) for child in children]
        self.child_dict = {child.path: child for child in self.children}

    def _generate_model_generator(self, model_string):
        """
        given a model_string that would return a queryset or model, create a function
        that will execute the string.
        """
        model_fn = """
def a(all_models, variables, models):
    return {}
"""

        ns = {}
        six.exec_(model_fn.format(model_string), ns)
        return ns['a']
        
    def _create_matcher(self):
        """
        determine type of path part and generate the search key and any supporting info

        creates the match method that returns a dict of variables/values if there
        is a match, or null if there is not.
        """
        match = splatRe.match(self.path)
        if match:
            self.variables = [match.groups()[0]]
            self.match = types.MethodType(is_splat_match, self)
        elif self.regex:
            self.regex = re.compile(self.path)
            self.variables = self.regex.groupindex.keys()
            self.match = types.MethodType(is_regex_match, self)
        else:
            self.variables = []
            self.match = types.MethodType(is_string_match, self)

    def __getitem__(self, val):
        return self.child_dict[val]

    def __repr__(self):
        return repr({'path': self.path, 'children': [x.path for x in self.children]})

    def traverse(self, request, path_remainder, variables, models, *args, **kwargs):
        """
        traverse this PathNode. 

        if this is the destination node return the view corresponding to the http method

        if this isn't the destination, traverse the children

        if the url doesn't resolve, through an http404.

        this method returns a tuple: (view, variables, models)
        """
        path_part = path_remainder[0]
        new_variables = self.match(path_part)

        # if new_variables is None, then we don't have a match, so return None
        if new_variables is None:
            return None

        # create the variables
        variables.update(new_variables)

        # create the model (if any)
        if hasattr(self, 'model'):
            models[self.name] = self.model

        # remove the path part that matches this node
        path_remainder.pop(0)

        if path_remainder:
            # if there is path left then, go through each child until we find one
            # that matches, pass its response up the tree
            for child in self.children:
                resp = child.traverse(request, path_remainder, variables, models)
                if resp is not None:
                    return resp
        else:
            # if there is no path left, then try to get the view that corresponds to
            # the request method and return it and the variables and models back up the tree
            try:
                return (self.views[request.method], variables, models)
            except:
                pass

        # if either we have a path_remainder that didn't match any children or we had
        # no path remainder and we didn't have a matching request method then we didn't find
        # a match for the url, so return 404.
        raise Http404

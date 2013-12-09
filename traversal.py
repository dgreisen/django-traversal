from __future__ import absolute_import, division, print_function, unicode_literals
import yaml as YAML
import re
from django.http import Http404
from collections import OrderedDict
import types
from django.utils import six

from .appring import apps as all_apps, models as all_models

splatRe = re.compile(r'^\<(\w*)(?:\|(\w*))?\>$')

def is_string_match(self, path_part):
    return {} if path_part == self.path else None

def is_regex_match(self, path_part):
    match = self.regex.match(path_part)
    return match.groupdict() if match else None

def is_splat_match(self, path_part):
    return {self.node_args[0]: path_part}

def is_int_match(self, path_part):
    try:
        return {self.node_args[0]: int(path_part)}
    except:
        return None

class PathArgContainer(dict):
    """
    an object for containing path_args created during traversal.
    """
    def __setitem__(self, key, value):
        if key in self:
            raise TypeError("path arg exists; cannot be overwritten")
        super(PathArgContainer, self).__setitem__(key, value)
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

def _parse_methods(config):
    """
    return all views contained in config; split views that are separated by commas.

    >>> _parse_methods({"GET": "fn1", "POST, PUT": "fn2", "other": "stuff})
    {"GET": "fn1", "POST": "fn2", "PUT": "fn2"}
    """
    out = {"views": {}}
    for k, v in config.items():
        # if all upper case, then it is a method
        if k.upper() == k:
            config.pop(k)       # remove from config
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
        passing the path_args and models accumulated during traversal
        """
        path = request.path.rstrip('/').split('/')
        view, path_args, node = self.root.traverse(request, path, PathArgContainer(), *args, **kwargs)
        kwargs.update(path_args)
        kwargs["node"] = node
        return view(request, *args, **kwargs)

    def test_traverse(self, request, *args, **kwargs):
        """
        traverse the PathTree, just as in traverse, but instead of getting the result the traverse,
        return a tuple of the view, accumulated path_args and accumulated models. Useful for unittesting.
        """
        path = request.path.rstrip('/').split('/')
        return self.root.traverse(request, path, PathArgContainer(), *args, **kwargs)

def get_function(path):
    """
    get a function defined by path from the apps object.
    """
    ns = {"all_apps": all_apps}
    six.exec_('a=' + path, ns)
    return ns['a']



class PathNode(object):
    def __init__(self, path="", parent=None, regex=False, name=None, children=[], **config):
        self.path = path
        self.parent = parent
        self.regex = regex

        # create the matching function
        self._create_matcher()

        # set name
        self.name = name or (self.node_args[0] if len(self.node_args) == 1 else self.path)

        # create views
        self.views = _parse_methods(config)['views']

        # set the config dict that is used by __getattr__
        self._config = {k: self._process_conf_item(v, k in self._force_fns) for k, v in config.items()}
        self._config_values = {}    # where lazily created values are stored

        # create children and index
        self.children = [PathNode(parent=self, **child) for child in children]
        self.child_dict = {child.path: child for child in self.children}

    # list of all config names that should be forced to be functions, even if they don't have >>>
    _force_fns = ["model", "qs"]

    # populated during traversal
    path_args = None

    def __getattr__(self, name):
        if name in self._config:
            if name not in self._config_values:
                out = self._config[name]
                if hasattr(out, "__call__"):
                    out = out(all_models, all_apps, self.path_args, self, self.parent)
                self._config_values[name] = out
            return self._config_values[name]
        raise AttributeError("'PathNode' object has no attribute '{}'".format(name))

    def refresh(self, name):
        """
        regenerate a conf value from conf function
        """
        if name in self._config_values:
            del self._config_values[name]
        return getattr(self, name)

    def _process_conf_item(self, item, fn=False):
        """
        process an item. item could be anything. if it is a string representing
        a function, convert to function. otherwise, pass through.
        """
        model_fn = """
def a(all_models, all_apps, path_args, node, parent):
    return {}
"""
        if not hasattr(item, "strip"):
            return item
        if ">>>" in item and item.index(">>>") == 0:
            item = item[3:].strip()
            fn = True
        if fn:
            ns = {}
            six.exec_(model_fn.format(item), ns)
            return ns['a']
        else:
            return item

    def _create_matcher(self):
        """
        determine type of path part and generate the search key and any supporting info

        creates the match method that returns a dict of node_args/values if there
        is a match, or null if there is not.
        """
        match = splatRe.match(self.path)
        if match:
            g = match.groups()
            self.node_args = [g[0]]
            if g[1] == "d":
                self.match = types.MethodType(is_int_match, self)
            else:
                self.match = types.MethodType(is_splat_match, self)
        elif self.regex:
            self.regex = re.compile(self.path)
            self.node_args = self.regex.groupindex.keys()
            self.match = types.MethodType(is_regex_match, self)
        else:
            self.node_args = []
            self.match = types.MethodType(is_string_match, self)

    def __getitem__(self, val):
        return self.child_dict[val]

    def __repr__(self):
        return repr({'path': self.path, 'children': [x.path for x in self.children]})

    def traverse(self, request, path_remainder, path_args, *args, **kwargs):
        """
        traverse this PathNode. 

        if this is the destination node return the view corresponding to the http method

        if this isn't the destination, traverse the children

        if the url doesn't resolve, through an http404.

        this method returns a tuple: (view, path_args)
        """
        # reset all stored config values
        self._config_values = {}
        # set the path_args
        self.path_args = path_args

        path_part = path_remainder[0]
        new_path_args = self.match(path_part)

        # if new_path_args is None, then we don't have a match, so return None
        if new_path_args is None:
            return None

        # create the path_args
        path_args.update(new_path_args)

        # remove the path part that matches this node
        path_remainder.pop(0)

        if path_remainder:
            # if there is path left then, go through each child until we find one
            # that matches, pass its response up the tree
            for child in self.children:
                resp = child.traverse(request, path_remainder, path_args)
                if resp is not None:
                    return resp
        else:
            # if there is no path left, then try to get the view that corresponds to
            # the request method and return it and the path_args and node back up the tree
            try:
                return (self.views[request.method], path_args, self)
            except:
                pass

        # if either we have a path_remainder that didn't match any children or we had
        # no path remainder and we didn't have a matching request method then we didn't find
        # a match for the url, so return 404.
        raise Http404

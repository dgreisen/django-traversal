from django.test import TestCase
from .traversal import PathNode, PathTree, PathArgContainer, all_apps, all_models
from django.http import HttpRequest as Request, HttpResponse
from django.contrib.auth.models import User, Group

def testViewOne(request, node=None, *args, **kwargs):
    return HttpResponse("success")

def testViewTwo(request, node=None, *args, **kwargs):
    return node, args, kwargs

class TestPathTree(TestCase):
# creation
    def test_create_with_yaml(self):
        yaml = """
path: ""
children:
  - path: users
    model: all_models.auth.User.objects.all()
    GET: all_apps.auth.views.login
    children:
      - path: <user>
        model: models['users'].get(pk=path_args['user'])
        GET,POST: all_apps.auth.views.login
"""
        
        cut = PathTree(yaml=yaml)

        actual = cut.root['users']['<user>']

    def test_traverse_expect_return_httpresponse(self):
        yaml = """
path: ""
children:
  - path: users
    model: all_models.auth.User.objects.all()
    GET: all_apps.traversal.tests.testViewOne
    children:
      - path: <user>
        model: models['users'].get(pk=path_args['user'])
        GET,POST: all_apps.traversal.tests.testViewOne
"""
        request = Request()
        request.path = "/users/1"
        request.method = "GET"

        cut = PathTree(yaml=yaml)

        actual = cut.traverse(request, *[], **{})

        self.assertIsInstance(actual, HttpResponse)

    def test_traverse_expect_call_view_with_node_and_kwargs_updated_with_path_args(self):
        yaml = """
path: ""
children:
  - path: users
    model: all_models.auth.User.objects.all()
    GET: all_apps.traversal.tests.testViewOne
    children:
      - path: <user>
        model: models['users'].get(pk=path_args['user'])
        GET,POST: all_apps.traversal.tests.testViewTwo
"""
        request = Request()
        request.path = "/users/1"
        request.method = "GET"

        cut = PathTree(yaml=yaml)

        actual = cut.traverse(request, *[], **{'hello': 'world'})

        self.assertIsInstance(actual[0], PathNode)
        self.assertEqual(actual[2], {'hello': 'world', 'user': "1"})

    def test_test_traverse_expect_return_view_func_path_args_nodes(self):
        yaml = """
path: ""
children:
  - path: users
    model: all_models.auth.User.objects.all()
    GET: all_apps.traversal.tests.testViewOne
    children:
      - path: <user>
        model: models['users'].get(pk=path_args['user'])
        GET,POST: all_apps.traversal.tests.testViewOne
"""
        request = Request()
        request.path = "/users/1"
        request.method = "GET"

        cut = PathTree(yaml=yaml)

        actual = cut.test_traverse(request, *[], **{})

        self.assertTrue(hasattr(actual[0], "__class__"))
        self.assertIsInstance(actual[1], PathArgContainer)
        self.assertIsInstance(actual[2], PathNode)

class TestPathNode(TestCase):
# creation
    def test_has_self_path(self):
        cut = PathNode(path="test")
        
        actual = cut.path
        self.assertEqual(actual, "test")

    def test_has_parent(self):
        parent = PathNode(path="", children=[{"path": "first"}, {"path": "second"}])
        
        cut = parent['first']

        actual = cut.parent
        self.assertEqual(actual, parent)

    def test_created_with_regex_path_expect_name_to_be_variable_name(self):
        cut = PathNode(path="^(?P<id>\d*)$", regex=True)

        actual = cut.name
        self.assertEqual(actual, 'id')

    def test_created_with_string_path_expect_name_to_be_string(self):
        cut = PathNode(path="test", regex=True)

        actual = cut.name
        self.assertEqual(actual, 'test')

    def test_created_with_splat_path_expect_name_to_be_variable_name(self):
        cut = PathNode(path="<id>")
        
        actual = cut.name
        self.assertEqual(actual, 'id')

    def test_created_with_regex_path_expect_path_args_to_list_path_args(self):
        cut = PathNode(path="^(?P<id>\d*)$", regex=True)

        actual = cut.node_args
        self.assertEqual(actual, ['id'])

    def test_created_with_splat_path_expect_path_args_to_list_path_args(self):
        cut = PathNode(path="<id>")
        
        actual = cut.node_args
        self.assertEqual(actual, ['id'])

    def test_created_with_name_override_default_name(self):
        cut = PathNode(path='<id>', name='test')

        actual = cut.name

        self.assertEqual(actual, 'test')

    def test_created_with_children_creates_children_accessible_via_getitem__(self):
        cut = PathNode(path="", children=[{"path": "first"}, {"path": "second"}])
        
        actual = cut["first"]
        self.assertIsInstance(actual, PathNode)

        actual = cut["second"]
        self.assertIsInstance(actual, PathNode)

    def test_created_with_GET_POST_creates_GET_POST_views(self):
        cut = PathNode(path="", GET="all_apps.auth.views.login", POST="all_apps.auth.views.login")

        actual = cut.views

        self.assertEqual(actual, {"GET": all_apps.auth.views.login, "POST": all_apps.auth.views.login})

    def test_created_with_child_GET_comma_POST_creates_GET_POST_views_for_child(self):
        cut = PathNode(path="", children=[{"path": "first", "GET, POST": "all_apps.auth.views.login"}])

        actual = cut["first"].views

        self.assertEqual(actual, {"GET": all_apps.auth.views.login, "POST": all_apps.auth.views.login})

    def test_created_with_config_expect_config_args_accessible_via_attributes(self):
        cut = PathNode(path="", conf1="hello")

        actual = cut.conf1

        self.assertEqual(actual, "hello")

    def test_created_with_config_arg_with_prompt_expect_config_to_be_property(self):
        cut = PathNode(path="", conf1=">>> 4*3")

        actual = cut.conf1

        self.assertEqual(actual, 12)

# __getattr__
    def test_getattr_returns_attributeerror_if_not_in_conf(self):
        cut = PathNode(path="", conf1="hello")

        with self.assertRaises(AttributeError):
            actual = cut.conf2

    def test_getattr_only_runs_fn_once_stores_value_for_future_getitems(self):
        cut = PathNode(path="", conf1=">>> []")

        first_call = cut.conf1

        actual = cut = cut.conf1

        self.assertIs(actual, first_call)

# refresh
    def test_refresh_with_conf_value_ensures_value_regenerated_by_fn(self):
        cut = PathNode(path="", conf1=">>> []")

        first_call = cut.conf1

        actual = cut = cut.refresh('conf1')

        self.assertIsNot(actual, first_call)

# process_conf_item
    def test_process_conf_item_when_passed_fn_flag_and_queryset_string_returns_queryset_generator(self):
        cut = PathNode()

        actual = cut._process_conf_item("all_models.auth.User.objects.all()", True)(all_models, all_apps, None, None, None)

        self.assertIsInstance(actual, type(all_models.auth.User.objects.all()))

    def test_process_conf_item_when_passed_fn_flag_and_string_returns_queryset_generator(self):
        user = User(username='abcd')
        user.save()
        cut = PathNode()._process_conf_item("all_models.auth.User.objects.get(username='abcd')", True)

        actual = cut(all_models, all_apps, None, None, None)

        self.assertEqual(actual, user)

    def test_process_conf_item_when_passed_fn_flag_and_string_using_variable_expect_returns_queryset_generator(self):
        user = User(username='abcd')
        user.save()

        cut = PathNode()._process_conf_item("all_models.auth.User.objects.get(pk=path_args['id'])", True)

        path_args = PathArgContainer()
        path_args["id"] = user.id

        actual =  cut(all_models, all_apps, path_args, None, None)

        self.assertEqual(actual, user)

    def test_process_conf_item_when_passed_fn_flag_and_string_using_node_expect_returns_queryset_generator(self):
        user = User(username='abcd')
        user.save()

        cut = PathNode()._process_conf_item("node.model.get(username='abcd')", True)

        actual =  cut(all_models, all_apps, None, PathNode(model="all_models.auth.User.objects.all()"), None)

        self.assertEqual(actual, user)

    def test_process_conf_item_when_passed_string_with_prompt_expect_function(self):
        cut = PathNode()._process_conf_item(">>> 5*4")

        actual = cut(all_models, all_apps, None, None, None)

        self.assertEqual(actual, 20)

    def test_process_conf_item_when_passed_string_without_prompt_expect_string(self):
        cut = PathNode()

        actual = cut._process_conf_item("5*4")

        self.assertEqual(actual, "5*4")

    def test_process_conf_item_when_passed_fn_flag_and_string_with_prompt_expect_function(self):
        cut = PathNode()._process_conf_item(">>> 5*4", True)

        actual = cut(all_models, all_apps, None, None, None)

        self.assertEqual(actual, 20)

# match
    def test_match_when_passed_string_matching_path_expect_empty_list(self):
        cut = PathNode(path="test")

        actual = cut.match('test')

        self.assertEqual(actual, {})

    def test_match_when_passed_string_not_matching_path_expect_none(self):
        cut = PathNode(path="test")

        actual = cut.match('hello')

        self.assertIsNone(actual)

    def test_match_when_passed_string_matching_regex_path_expect_dict_with_path_args(self):
        cut = PathNode(path="^(?P<id>\d*)$", regex=True)

        actual = cut.match('43')

        self.assertEqual(actual, {"id": "43"})

    def test_match_when_passed_string_not_matching_regex_path_expect_none(self):
        cut = PathNode(path="^(?P<id>\d*)$", regex=True)

        actual = cut.match('hello')

        self.assertIsNone(actual)

    def test_match_when_passed_string_matching_splat_expect_dict_with_path_args(self):
        cut = PathNode(path="<id>")
        
        actual = cut.match("hello")
        self.assertEqual(actual, {"id": "hello"})

    def test_match_when_passed_string_matching_int_splat_expect_dict_with_int_path_arg(self):
        cut = PathNode(path="<id|d>")
        
        actual = cut.match("5")
        self.assertEqual(actual, {"id": 5})

    def test_match_when_passed_string_not_matching_int_splat_expect_none(self):
        cut = PathNode(path="<id|d>")
        
        actual = cut.match("h5n1")
        self.assertIsNone(actual)

# traverse
    def test_after_traverse_expect_path_args_attribute_exists(self):
        path_args = PathArgContainer()
        req = Request()
        req.method = "GET"
        cut = PathNode(path="", children=[{"path": "first"}, {"path": "second"}], GET="all_apps.auth.views.login")

        cut.traverse(req, [""], path_args)

        actual = cut.path_args

        self.assertEqual(actual, path_args)

    def test_after_traverse_expect_model_attribute_exists(self):
        req = Request()
        req.method = "GET"
        user = User(username="testuser")
        user.save()
        cut = PathNode(path="", children=[{"path": "first"}, {"path": "second"}], GET="all_apps.auth.views.login", model="all_models.auth.User.objects.get(pk={})".format(user.id))

        cut.traverse(req, [""], PathArgContainer())

        actual = cut.model

        self.assertEqual(actual, user)

    def test_config_refreshed_after_traverse(self):
        req = Request()
        req.method = "GET"
        cut = PathNode(path="", test= ">>> []", children=[{"path": "first"}, {"path": "second"}], GET="all_apps.auth.views.login")

        first_call = cut.test

        cut.traverse(req, [""], PathArgContainer())

        actual = cut.test

        self.assertIsNot(actual, first_call)


    def test_traverse_one_path_remainder(self):
        req = Request()
        req.method = "GET"
        pathNode = PathNode(path="", children=[{"path": "first"}, {"path": "second"}], GET="all_apps.auth.views.login")
        result = pathNode.traverse(req, [""], PathArgContainer())
        self.assertEqual(result[0], all_apps.auth.views.login)

    def test_traverse_two_path_remainder(self):
        req = Request()
        req.method = "GET"
        pathNode = PathNode(path="", children=[{"path": "first", "GET": "all_apps.auth.views.logout"}, {"path": "second"}], GET="all_apps.auth.views.login")
        result = pathNode.traverse(req, ['', 'first'], PathArgContainer())
        self.assertEqual(result[0], all_apps.auth.views.logout)

    def test_traverse_returns_variable(self):
        req = Request()
        req.method = "GET"
        pathNode = PathNode(path="<user>", GET="all_apps.auth.views.login")
        result = pathNode.traverse(req, ["1"], PathArgContainer())
        self.assertEqual(result[1]['user'], "1")

    def test_traverse_returns_node(self):
        user = all_models.auth.User(username='testuser')
        user.save()
        req = Request()
        req.method = "GET"

        cut = PathNode(path="<user>", GET="all_apps.auth.views.login", model="all_models.auth.User.objects.get(pk=path_args['user'])")

        actual = cut.traverse(req, [str(user.id)], PathArgContainer())

        self.assertIsInstance(actual[2], PathNode)


class TestPathArgContainer(TestCase):
    def test_getitem_returns_value_of_fn_stored_by_setitem(self):
        cut = PathArgContainer()

        cut["test"] = 5

        actual = cut["test"]

        self.assertEqual(actual, 5)

    def test_setitem_called_with_existing_key_expect_raise_typeerror(self):
        cut = PathArgContainer()

        cut["test"] = 5

        with self.assertRaises(TypeError):
            cut["test"] = 8

    def test_update_called_with_dict_update_self(self):
        cut = PathArgContainer()
        cut["test"] = 5

        cut.update({"hello": "world"})

        self.assertEqual(cut, {"test": 5, "hello": "world"})

    def test_update_called_with_dict_with_existing_key_expect_raise_typeerror(self):
        cut = PathArgContainer()
        cut["test"] = 5

        with self.assertRaises(TypeError):
            cut.update({"test": 8, "hello": "world"})

    def test_update_stores_update_values_in_current_dict(self):
        cut = PathArgContainer()
        cut["test"] = 5

        cut.update({"hello": "world", "goto": 10})

        actual = cut.current

        self.assertEqual(actual, {"hello": "world", "goto": 10})

    def test_setitem_stores_most_recently_set_item_in_current_dict(self):
        cut = PathArgContainer()

        cut["test"] = 5

        actual = cut.current
        self.assertEqual(actual, {"test": 5})


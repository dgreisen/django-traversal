from django.test import TestCase
from traversal import PathNode, PathTree, ModelContainer, VariableContainer, all_apps, all_models
from django.http import HttpRequest as Request, HttpResponse
from django.contrib.auth.models import User, Group

def testView(request, models=None, variables=None, *args, **kwargs):
    return HttpResponse("success")

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
        model: models['users'].get(pk=variables['user'])
        GET,POST: all_apps.auth.views.login
"""
        
        cut = PathTree(yaml=yaml)

        actual = cut.root['users']['<user>']

    def test_traverse_expect_return_http_response(self):
        yaml = """
path: ""
children:
  - path: users
    model: all_models.auth.User.objects.all()
    GET: all_apps.traverse.tests.testView
    children:
      - path: <user>
        model: models['users'].get(pk=variables['user'])
        GET,POST: all_apps.traverse.tests.testView
"""
        request = Request()
        request.path = "/users/1"
        request.method = "GET"

        cut = PathTree(yaml=yaml)

        actual = cut.traverse(request, *[], **{})

        self.assertIsInstance(actual, HttpResponse)

    def test_test_traverse_expect_return_view_func_variables_models(self):
        yaml = """
path: ""
children:
  - path: users
    model: all_models.auth.User.objects.all()
    GET: all_apps.traverse.tests.testView
    children:
      - path: <user>
        model: models['users'].get(pk=variables['user'])
        GET,POST: all_apps.traverse.tests.testView
"""
        request = Request()
        request.path = "/users/1"
        request.method = "GET"

        cut = PathTree(yaml=yaml)

        actual = cut.test_traverse(request, *[], **{})

        self.assertTrue(hasattr(actual[0], "__class__"))
        self.assertIsInstance(actual[1], VariableContainer)
        self.assertIsInstance(actual[2], ModelContainer)

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

    def test_created_with_regex_path_expect_variables_to_list_variables(self):
        cut = PathNode(path="^(?P<id>\d*)$", regex=True)

        actual = cut.variables
        self.assertEqual(actual, ['id'])

    def test_created_with_splat_path_expect_variables_to_list_variables(self):
        cut = PathNode(path="<id>")
        
        actual = cut.variables
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

    def test_created_with_queryset_creates_model_function_that_returns_queryset(self):
        cut = PathNode(path="users", model="all_models.auth.User.objects.all()")
        
        actual = cut.model(all_models, VariableContainer(), ModelContainer())

        self.assertIsInstance(actual, type(all_models.auth.User.objects.all()))

    def test_created_with_GET_POST_creates_GET_POST_views(self):
        cut = PathNode(path="", GET="all_apps.auth.views.login", POST="all_apps.auth.views.login")

        actual = cut.views

        self.assertEqual(actual, {"GET": all_apps.auth.views.login, "POST": all_apps.auth.views.login})

    def test_created_with_child_GET_comma_POST_creates_GET_POST_views_for_child(self):
        cut = PathNode(path="", children=[{"path": "first", "GET, POST": "all_apps.auth.views.login"}])

        actual = cut["first"].views

        self.assertEqual(actual, {"GET": all_apps.auth.views.login, "POST": all_apps.auth.views.login})

# model/queryset generator function
    def test_generate_model_generator_when_passed_queryset_string_returns_queryset_generator(self):
        cut = PathNode()

        actual = cut._generate_model_generator("all_models.auth.User.objects.all()")(all_models, None, None)

        self.assertIsInstance(actual, type(all_models.auth.User.objects.all()))

    def test_generate_model_generator_when_passed_model_string_returns_queryset_generator(self):
        user = User(username='abcd')
        user.save()
        cut = PathNode()._generate_model_generator("all_models.auth.User.objects.get(username='abcd')")

        actual = cut(all_models, None, None)

        self.assertEqual(actual, user)

    def test_generate_model_generator_when_passed_model_string_using_variable_expect_returns_queryset_generator(self):
        user = User(username='abcd')
        user.save()

        cut = PathNode()._generate_model_generator("all_models.auth.User.objects.get(pk=variables['id'])")

        variables = VariableContainer()
        variables["id"] = user.id

        actual =  cut(all_models, variables, None)

        self.assertEqual(actual, user)

    def test_generate_model_generator_when_passed_model_string_using_model_expect_returns_queryset_generator(self):
        user = User(username='abcd')
        user.save()

        cut = PathNode()._generate_model_generator("models['users'].get(username='abcd')")

        models = ModelContainer()
        models['users'] = PathNode()._generate_model_generator("all_models.auth.User.objects.all()")

        actual =  cut(all_models, None, models)

        self.assertEqual(actual, user)

# match
    def test_match_when_passed_string_matching_path_expect_empty_list(self):
        cut = PathNode(path="test")

        actual = cut.match('test')

        self.assertEqual(actual, {})

    def test_match_when_passed_string_not_matching_path_expect_none(self):
        cut = PathNode(path="test")

        actual = cut.match('hello')

        self.assertEqual(actual, None)

    def test_match_when_passed_string_matching_regex_path_expect_dict_with_variables(self):
        cut = PathNode(path="^(?P<id>\d*)$", regex=True)

        actual = cut.match('43')

        self.assertEqual(actual, {"id": "43"})

    def test_match_when_passed_string_not_matching_regex_path_expect_none(self):
        cut = PathNode(path="^(?P<id>\d*)$", regex=True)

        actual = cut.match('hello')

        self.assertEqual(actual, None)

    def test_match_when_passed_string_matching_splat_expect_dict_with_variables(self):
        cut = PathNode(path="<id>")
        
        actual = cut.match("hello")
        self.assertEqual(actual, {"id": "hello"})

# traverse
    def test_traverse_one_path_remainder(self):
        req = Request()
        req.method = "GET"
        pathNode = PathNode(path="", children=[{"path": "first"}, {"path": "second"}], GET="all_apps.auth.views.login")
        result = pathNode.traverse(req, [""], VariableContainer(), ModelContainer())
        self.assertEqual(result[0], all_apps.auth.views.login)

    def test_traverse_two_path_remainder(self):
        req = Request()
        req.method = "GET"
        pathNode = PathNode(path="", children=[{"path": "first", "GET": "all_apps.auth.views.logout"}, {"path": "second"}], GET="all_apps.auth.views.login")
        result = pathNode.traverse(req, ['', 'first'], VariableContainer(), ModelContainer())
        self.assertEqual(result[0], all_apps.auth.views.logout)

    def test_traverse_returns_variable(self):
        req = Request()
        req.method = "GET"
        pathNode = PathNode(path="<user>", GET="all_apps.auth.views.login")
        result = pathNode.traverse(req, ["1"], VariableContainer(), ModelContainer())
        self.assertEqual(result[1]['user'], "1")

    def test_traverse_returns_model(self):
        variablecontainer = VariableContainer()
        modelcontainer = ModelContainer(variables=variablecontainer)
        user = all_models.auth.User(username='testuser')
        user.save()
        req = Request()
        req.method = "GET"

        cut = PathNode(path="<user>", GET="all_apps.auth.views.login", model="all_models.auth.User.objects.get(pk=variables['user'])")

        actual = cut.traverse(req, [str(user.id)], variablecontainer, modelcontainer)

        self.assertEqual(actual[2]["user"], user)

class TestModelContainer(TestCase):
    def test_create_when_passed_variablecontainer_expect_add_variables_attribute(self):
        variables = VariableContainer()

        cut = ModelContainer(variables=variables)

        actual = cut.variables

        self.assertIs(actual, variables)

    def test_create_when_not_passed_variablecontainer_expect_add_empty_variables_attribute(self):
        cut = ModelContainer()

        actual = cut.variables

        self.assertIsInstance(actual, VariableContainer)

    def test_getitem_returns_value_of_fn_stored_by_setitem(self):
        cut = ModelContainer()

        def fn(*args, **kwargs):
            return []

        cut["test"] = fn

        actual = cut["test"]

        self.assertEqual(actual, fn())

    def test_getitem_only_runs_fn_once_stores_value_for_future_getitems(self):
        cut = ModelContainer()

        def fn(*args, **kwargs):
            return []

        cut["test"] = fn

        first_call = cut["test"]

        actual = cut["test"]
        self.assertIs(actual, first_call)

    def test_setitem_called_with_existing_key_expect_raise_typeerror(self):
        cut = ModelContainer()

        def fn(*args, **kwargs):
            return []

        cut["test"] = fn

        with self.assertRaises(TypeError):
            cut["test"] = fn

    def test_getitem_expect_passes_all_models_to_fn(self):
        cut = ModelContainer()

        def fn(*args, **kwargs):
            return args

        cut["test"] = fn

        actual = cut["test"]

        self.assertEqual(actual[0], all_models)

    def test_getitem_expect_passes_variables_to_fn(self):
        cut = ModelContainer()

        def fn(*args, **kwargs):
            return args

        cut["test"] = fn

        actual = cut["test"]

        self.assertIsInstance(actual[1], VariableContainer)

    def test_getitem_expect_passes_models_to_fn(self):
        cut = ModelContainer()

        def fn(*args, **kwargs):
            return args

        cut["test"] = fn

        actual = cut["test"]

        self.assertIsInstance(actual[2], ModelContainer)

    def test_setitem_stores_most_recently_set_item_in_current(self):
        cut = ModelContainer()

        def fn(*args, **kwargs):
            return []

        cut["test"] = fn

        actual = cut.current
        self.assertIs(actual, cut["test"])

    def test_db_refresh_when_passed_key_expect_refresh_from_function_at_key(self):
        cut = ModelContainer()

        def fn(*args, **kwargs):
            return []

        cut["test"] = fn

        first_call = cut["test"]

        actual = cut.db_refresh("test")
        self.assertIsNot(actual, first_call)

        actual2 = cut["test"]

        self.assertIs(actual, actual2)

class TestVariableContainer(TestCase):
    def test_getitem_returns_value_of_fn_stored_by_setitem(self):
        cut = VariableContainer()

        cut["test"] = 5

        actual = cut["test"]

        self.assertEqual(actual, 5)

    def test_setitem_called_with_existing_key_expect_raise_typeerror(self):
        cut = VariableContainer()

        cut["test"] = 5

        with self.assertRaises(TypeError):
            cut["test"] = 8

    def test_update_called_with_dict_update_self(self):
        cut = VariableContainer()
        cut["test"] = 5

        cut.update({"hello": "world"})

        self.assertEqual(cut, {"test": 5, "hello": "world"})

    def test_update_called_with_dict_with_existing_key_expect_raise_typeerror(self):
        cut = VariableContainer()
        cut["test"] = 5

        with self.assertRaises(TypeError):
            cut.update({"test": 8, "hello": "world"})

    def test_update_stores_update_values_in_current_dict(self):
        cut = VariableContainer()
        cut["test"] = 5

        cut.update({"hello": "world", "goto": 10})

        actual = cut.current

        self.assertEqual(actual, {"hello": "world", "goto": 10})

    def test_setitem_stores_most_recently_set_item_in_current_dict(self):
        cut = VariableContainer()

        cut["test"] = 5

        actual = cut.current
        self.assertEqual(actual, {"test": 5})


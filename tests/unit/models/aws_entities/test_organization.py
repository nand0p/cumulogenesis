'''
Unit tests for cumulogenesis.models.aws_entities.organization
'''

import unittest
from unittest import mock
from cumulogenesis import exceptions
from cumulogenesis import helpers
from cumulogenesis.models.aws_entities import Organization

class TestOrganization(unittest.TestCase):
    '''
    Tests for cumulogenesis.models.aws_entities.organization.Organization
    '''

    def setUp(self):
        '''
        Set up tests
        '''
        self.dummy_root_account_id = '123456789'

    def _get_base_organization(self):
        return Organization(root_account_id=self.dummy_root_account_id)

    @staticmethod
    def _add_name_to_entity_mocks(mock_dict):
        '''
        Helper to aid in adding "name" properties to mock.Mock instances
        '''
        for entity_name in mock_dict:
            mock_dict[entity_name].name = entity_name
        return mock_dict

    def test_raise_if_invalid_when_invalid(self):
        '''
        Test Organization.raise_if_invalid when problems found

        When Organization.validate() returns problems, it should raise
        exceptions.InvalidOrganizationException
        '''
        with mock.patch('cumulogenesis.models.aws_entities.Organization.validate') as validate_mock:
            validate_mock.return_value = {"accounts": {"not-a-real-account": ["some_problem"]}}
            org = self._get_base_organization()
            with self.assertRaises(exceptions.InvalidOrganizationException):
                org.raise_if_invalid()

    def test_raise_if_invalid_when_valid(self):
        '''
        Test Organization.raise_if_invalid when no problems are found

        When Organization.validate() returns no problems, it should not raise
        exceptions.InvalidOrganizationException
        '''
        with mock.patch('cumulogenesis.models.aws_entities.Organization.validate') as validate_mock:
            validate_mock.return_value = {}
            org = self._get_base_organization()
            try:
                org.raise_if_invalid()
            except exceptions.InvalidOrganizationException:
                self.fail('exceptions.InvalidOrganizationException raised unexpectedly')

    def test_get_orgunit_hierarchy_valid(self):
        '''
        Test Organization._get_orgunit_hierarchy when no orphans

        When the Organization contains no orphans, a nested dict representing
        the Organizations's orgunit and account hierarchy should be returned
        that shouldn't contain the ORPHANED root key
        '''
        accounts_mock = {"account_a": mock.Mock(parent_references=['ou_a']),
                         "account_b": mock.Mock(parent_references=['ou_b']),
                         "account_c": mock.Mock(parent_references=['ou_c'])}
        orgunits_mock = {"ou_a": mock.Mock(parent_orgunit=None, accounts=["account_a"]),
                         "ou_b": mock.Mock(parent_orgunit="ou_a", accounts=["account_b"]),
                         "ou_c": mock.Mock(parent_orgunit=None, accounts=["account_c"])}
        org = self._get_base_organization()
        org.orgunits = self._add_name_to_entity_mocks(orgunits_mock)
        org.accounts = self._add_name_to_entity_mocks(accounts_mock)
        expected_hierarchy = {
            "ROOT_ACCOUNT": {
                "orgunits": {
                    "ou_a": {
                        "accounts": ["account_a"],
                        "orgunits": {
                            "ou_b": {"accounts": ["account_b"]}}},
                    "ou_c": {
                        "accounts": ["account_c"]}}}}
        hierarchy = org.get_orgunit_hierarchy()
        print("Expected:", expected_hierarchy)
        print("Actual:", hierarchy)
        assert hierarchy == expected_hierarchy


    def test_get_orgunit_hierarchy_invalid_orphan(self):
        '''
        Test Organization._get_orgunit_hierarchy when orphans

        When the Organization contains orphans, the resulting hierarchy should
        contain an top level ORPHANED key containing the orphaned account.
        '''
        accounts_mock = {"account_a": mock.Mock(parent_references=['ou_a']),
                         "account_b": mock.Mock(parent_references=['ou_b']),
                         "account_c": mock.Mock(parent_references=[])}
        orgunits_mock = {"ou_a": mock.Mock(parent_orgunit=None, accounts=["account_a"]),
                         "ou_b": mock.Mock(parent_orgunit="ou_a", accounts=["account_b"]),
                         "ou_c": mock.Mock(parent_orgunit=None, accounts=[])}
        org = self._get_base_organization()
        org.orgunits = self._add_name_to_entity_mocks(orgunits_mock)
        org.accounts = self._add_name_to_entity_mocks(accounts_mock)
        expected_hierarchy = {
            "ORPHANED": {"accounts": ["account_c"]},
            "ROOT_ACCOUNT": {
                "orgunits": {
                    "ou_a": {
                        "accounts": ["account_a"],
                        "orgunits": {
                            "ou_b": {"accounts": ["account_b"]}}},
                    "ou_c": {}}}}
        hierarchy = org.get_orgunit_hierarchy()
        print("Expected:", expected_hierarchy)
        print("Actual:", hierarchy)
        assert hierarchy == expected_hierarchy

    def test_regenerate_groups(self):
        '''
        Test Organization.regenerate_groups
        '''
        accounts_mock = {"account_a": mock.Mock(groups=['group_one']),
                         "account_b": mock.Mock(groups=['group_two']),
                         "account_c": mock.Mock(groups=[])}
        stacks_mock = {"stack_a": mock.Mock(groups=['group_one']),
                       "stack_b": mock.Mock(groups=['group_two']),
                       "stack_c": mock.Mock(groups=[], accounts=['account_c'])}
        org = self._get_base_organization()
        org.accounts = self._add_name_to_entity_mocks(accounts_mock)
        org.stacks = self._add_name_to_entity_mocks(stacks_mock)
        expected_groups = {
            "group_one": {"name": "group_one", "accounts": ["account_a"],
                          "stacks": ["stack_a"]},
            "group_two": {"name": "group_two", "accounts": ["account_b"],
                          "stacks": ["stack_b"]}}
        org.regenerate_groups()
        print("Expected:", expected_groups)
        print("Actual:", org.groups)
        assert expected_groups == org.groups

    def test_validate(self):
        '''
        Test Organization.validate

        This test should generate a problem for one of each potential
        invalid Organization state.
        '''
        orgunits_mock = {
            "missing_parent": mock.Mock(parent_orgunit="nonexistent", accounts=[], policies=[]),
            "missing_account": mock.Mock(parent_orgunit=None, accounts=["nonexistent"], policies=[]),
            "missing_policy": mock.Mock(parent_orgunit=None, accounts=[], policies=["nonexistent"]),
            "valid_ou_a": mock.Mock(parent_orgunit=None,
                                    accounts=["multiple_references", "valid_account_a"], policies=[]),
            "valid_ou_b": mock.Mock(parent_orgunit=None, accounts=["multiple_references"], policies=[])}
        accounts_mock = {
            "orphaned_account": mock.Mock(parent_references=None, groups=[], regions=["us-east-1"]),
            "multiple_references": mock.Mock(parent_references=None, groups=[], regions=["us-east-1"]),
            "valid_account_a": mock.Mock(parent_references=None, groups=[], regions=["us-east-1"])}
        stacks_mock = {
            "missing_account": mock.Mock(accounts=["nonexistent"], groups=[], orgunits=[]),
            "missing_orgunit": mock.Mock(accounts=[], groups=[], orgunits=["nonexistent"]),
            "valid_stack_a": mock.Mock(accounts=["valid_account_a"], groups=[], orgunits=[]),
            "missing_group": mock.Mock(accounts=[], groups=["nonexistent"], orgunits=[])}
        groups_mock = {"valid_group": {"accounts": ["valid_account_a"], "stacks": ["valid_stack_a"]},
                       "missing_accounts": {"accounts": [], "stacks": ["valid_stack_a"]},
                       "missing_stacks": {"accounts": ["valid_account_a"], "stacks": []}}
        # Patch Organization.regenerate_groups so it doesn't clobber our mock
        with mock.patch('cumulogenesis.models.aws_entities.Organization.regenerate_groups'):
            org = self._get_base_organization()
            org.orgunits = self._add_name_to_entity_mocks(orgunits_mock)
            org.accounts = self._add_name_to_entity_mocks(accounts_mock)
            org.stacks = self._add_name_to_entity_mocks(stacks_mock)
            org.groups = groups_mock
            expected_problems = {'orgunits': {'missing_parent': ['orphaned from parent nonexistent'],
                                              'missing_account': ['references missing account nonexistent'],
                                              'missing_policy': ['references missing policy nonexistent']},
                                 'accounts': {'orphaned_account': ['orphaned'],
                                              #pylint: disable=line-too-long
                                              'multiple_references': ['referenced as a child of multiple orgunits: valid_ou_a, valid_ou_b']},
                                 'stacks': {'missing_account': ['references missing account nonexistent'],
                                            'missing_group': ['references missing group nonexistent'],
                                            'missing_orgunit': ['references missing orgunit nonexistent']}}
            problems = org.validate()
            print("Expected:")
            helpers.pretty_print(expected_problems)
            print("Actual:")
            helpers.pretty_print(problems)
            assert expected_problems == problems

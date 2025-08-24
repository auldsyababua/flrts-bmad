"""
Regression test to ensure processor constructors maintain their correct signatures.

This test acts as a guardrail to prevent reverting to old constructor signatures
that included redis_store or user_id parameters. All processors should only
accept a supabase_client parameter.

Author: System Guard
Purpose: Prevent constructor signature regression
Critical: This test MUST pass for the system to work correctly
"""

import inspect
import unittest

from src.rails.processors.list_processor import ListProcessor

# Import the processors we need to test
from src.rails.processors.task_processor import TaskProcessor


class TestProcessorConstructorRegression(unittest.TestCase):
    """
    Regression tests to ensure processor constructors don't change back
    to old signatures with redis_store or user_id parameters.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.processors_to_test = [
            (TaskProcessor, "TaskProcessor"),
            (ListProcessor, "ListProcessor"),
        ]

        # These are the forbidden parameter names that should NOT appear
        self.forbidden_params = {"redis_store", "user_id", "redis", "user"}

        # The only allowed parameter (besides self)
        self.required_param = "supabase_client"

    def test_constructor_signatures_correct(self):
        """
        Test that all processor constructors have the correct signature.
        They should only accept 'supabase_client' as a parameter.
        """
        for processor_class, class_name in self.processors_to_test:
            with self.subTest(processor=class_name):
                # Get the constructor signature
                sig = inspect.signature(processor_class.__init__)
                params = sig.parameters

                # Get parameter names (excluding 'self')
                param_names = [name for name in params.keys() if name != "self"]

                # Check that we have exactly one parameter
                self.assertEqual(
                    len(param_names),
                    1,
                    f"{class_name}.__init__ should have exactly 1 parameter "
                    f"(besides 'self'), but has {len(param_names)}: {param_names}",
                )

                # Check that the parameter is 'supabase_client'
                self.assertEqual(
                    param_names[0],
                    self.required_param,
                    f"{class_name}.__init__ should accept 'supabase_client' "
                    f"but instead accepts '{param_names[0]}'",
                )

    def test_no_forbidden_parameters(self):
        """
        Test that none of the processors accept forbidden parameters
        like redis_store, user_id, redis, or user.
        """
        for processor_class, class_name in self.processors_to_test:
            with self.subTest(processor=class_name):
                # Get the constructor signature
                sig = inspect.signature(processor_class.__init__)
                params = sig.parameters

                # Get parameter names (excluding 'self')
                param_names = set(params.keys()) - {"self"}

                # Check for forbidden parameters
                forbidden_found = param_names.intersection(self.forbidden_params)

                self.assertEqual(
                    len(forbidden_found),
                    0,
                    f"{class_name}.__init__ contains forbidden parameter(s): "
                    f"{forbidden_found}. These parameters are from an old "
                    f"implementation and should NOT be present. "
                    f"The constructor should only accept 'supabase_client'.",
                )

    def test_parameter_has_no_default(self):
        """
        Test that supabase_client parameter is required (no default value).
        """
        for processor_class, class_name in self.processors_to_test:
            with self.subTest(processor=class_name):
                sig = inspect.signature(processor_class.__init__)
                params = sig.parameters

                # Check that supabase_client exists and has no default
                self.assertIn(
                    self.required_param,
                    params,
                    f"{class_name}.__init__ missing required parameter 'supabase_client'",
                )

                param = params[self.required_param]
                self.assertEqual(
                    param.default,
                    inspect.Parameter.empty,
                    f"{class_name}.__init__ parameter 'supabase_client' should be "
                    f"required (no default value), but has default: {param.default}",
                )

    def test_constructor_actually_works(self):
        """
        Test that constructors can be called with just supabase_client.
        This ensures they don't secretly require other parameters internally.
        """
        # We'll use a mock object as supabase_client
        mock_client = object()

        for processor_class, class_name in self.processors_to_test:
            with self.subTest(processor=class_name):
                try:
                    # Try to instantiate with just supabase_client
                    instance = processor_class(supabase_client=mock_client)

                    # Verify the instance was created
                    self.assertIsNotNone(
                        instance, f"Failed to create {class_name} instance"
                    )

                    # Verify it's the right type
                    self.assertIsInstance(
                        instance,
                        processor_class,
                        f"Created instance is not of type {class_name}",
                    )

                except TypeError as e:
                    # If we get a TypeError, it might mean the constructor
                    # expects additional parameters
                    self.fail(
                        f"{class_name} constructor failed with just 'supabase_client'. "
                        f"This suggests it may require additional parameters that "
                        f"weren't declared in the signature. Error: {e}"
                    )

    def test_inheritance_from_base_processor(self):
        """
        Verify that all processors inherit from BaseProcessor correctly
        and don't override __init__ with different signatures.
        """
        from src.rails.processors.base_processor import BaseProcessor

        for processor_class, class_name in self.processors_to_test:
            with self.subTest(processor=class_name):
                # Check inheritance
                self.assertTrue(
                    issubclass(processor_class, BaseProcessor),
                    f"{class_name} should inherit from BaseProcessor",
                )

                # Get BaseProcessor's __init__ signature
                base_sig = inspect.signature(BaseProcessor.__init__)
                base_params = set(base_sig.parameters.keys()) - {"self"}

                # Get processor's __init__ signature
                proc_sig = inspect.signature(processor_class.__init__)
                proc_params = set(proc_sig.parameters.keys()) - {"self"}

                # They should have the same parameters
                self.assertEqual(
                    proc_params,
                    base_params,
                    f"{class_name}.__init__ parameters {proc_params} don't match "
                    f"BaseProcessor.__init__ parameters {base_params}. "
                    f"All processors should have consistent constructor signatures.",
                )

    def test_error_message_clarity(self):
        """
        Test that if someone tries to instantiate with old parameters,
        they get a clear error message.
        """
        mock_client = object()
        mock_redis = object()
        mock_user_id = "test_user"

        for processor_class, class_name in self.processors_to_test:
            with self.subTest(processor=class_name):
                # Try with redis_store (old parameter)
                with self.assertRaises(TypeError) as cm:
                    processor_class(supabase_client=mock_client, redis_store=mock_redis)

                error_msg = str(cm.exception)
                self.assertIn(
                    "unexpected keyword argument",
                    error_msg.lower(),
                    f"Error message for {class_name} with redis_store should "
                    f"mention unexpected keyword argument",
                )

                # Try with user_id (old parameter)
                with self.assertRaises(TypeError) as cm:
                    processor_class(supabase_client=mock_client, user_id=mock_user_id)

                error_msg = str(cm.exception)
                self.assertIn(
                    "unexpected keyword argument",
                    error_msg.lower(),
                    f"Error message for {class_name} with user_id should "
                    f"mention unexpected keyword argument",
                )


if __name__ == "__main__":
    # Run with verbose output to see all test results
    unittest.main(verbosity=2)

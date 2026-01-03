"""Tests for the cross-agent memory store implementations."""

import asyncio
import os
import shutil
import tempfile
import unittest
from datetime import datetime

from core.memory import (
    Memory,
    FileMemoryStore,
    SQLiteMemoryStore,
    get_memory_store,
)


class TestMemoryModel(unittest.TestCase):
    """Tests for the Memory model."""

    def test_memory_creation(self):
        """Test creating a Memory instance."""
        memory = Memory(
            key="test_key",
            value={"data": "test_value"},
            namespace=("project", "agent"),
            metadata={"source": "test"}
        )

        self.assertEqual(memory.key, "test_key")
        self.assertEqual(memory.value, {"data": "test_value"})
        self.assertEqual(memory.namespace, ("project", "agent"))
        self.assertEqual(memory.metadata, {"source": "test"})
        self.assertIsInstance(memory.timestamp, datetime)

    def test_memory_defaults(self):
        """Test Memory default values."""
        memory = Memory(key="test", value="value")

        self.assertEqual(memory.metadata, {})
        self.assertEqual(memory.namespace, ())
        self.assertIsNotNone(memory.timestamp)


class TestFileMemoryStore(unittest.TestCase):
    """Tests for the FileMemoryStore implementation."""

    def setUp(self):
        """Create a temporary directory for test storage."""
        self.test_dir = tempfile.mkdtemp()
        self.store = FileMemoryStore(
            file_path=os.path.join(self.test_dir, "test_memories.json")
        )

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_store_and_retrieve(self):
        """Test storing and retrieving a memory."""
        async def run_test():
            namespace = ("project-x", "agent-1")
            key = "test_memory"
            value = {"commit": "abc123", "duration": 45}
            metadata = {"type": "build"}

            await self.store.store(namespace, key, value, metadata)
            memory = await self.store.retrieve(namespace, key)

            self.assertIsNotNone(memory)
            self.assertEqual(memory.key, key)
            self.assertEqual(memory.value, value)
            self.assertEqual(memory.metadata, metadata)
            self.assertEqual(memory.namespace, namespace)

        asyncio.run(run_test())

    def test_retrieve_nonexistent(self):
        """Test retrieving a non-existent memory."""
        async def run_test():
            memory = await self.store.retrieve(("test",), "nonexistent")
            self.assertIsNone(memory)

        asyncio.run(run_test())

    def test_update_existing(self):
        """Test updating an existing memory."""
        async def run_test():
            namespace = ("test",)
            key = "update_test"

            await self.store.store(namespace, key, "value1")
            await self.store.store(namespace, key, "value2")

            memory = await self.store.retrieve(namespace, key)
            self.assertEqual(memory.value, "value2")

        asyncio.run(run_test())

    def test_list_keys(self):
        """Test listing keys in a namespace."""
        async def run_test():
            namespace = ("test", "keys")

            await self.store.store(namespace, "key1", "value1")
            await self.store.store(namespace, "key2", "value2")
            await self.store.store(namespace, "key3", "value3")

            keys = await self.store.list_keys(namespace)
            self.assertEqual(sorted(keys), ["key1", "key2", "key3"])

        asyncio.run(run_test())

    def test_list_keys_empty(self):
        """Test listing keys in an empty namespace."""
        async def run_test():
            keys = await self.store.list_keys(("nonexistent",))
            self.assertEqual(keys, [])

        asyncio.run(run_test())

    def test_delete(self):
        """Test deleting a memory."""
        async def run_test():
            namespace = ("test",)
            key = "delete_test"

            await self.store.store(namespace, key, "value")
            deleted = await self.store.delete(namespace, key)
            self.assertTrue(deleted)

            memory = await self.store.retrieve(namespace, key)
            self.assertIsNone(memory)

        asyncio.run(run_test())

    def test_delete_nonexistent(self):
        """Test deleting a non-existent memory."""
        async def run_test():
            deleted = await self.store.delete(("test",), "nonexistent")
            self.assertFalse(deleted)

        asyncio.run(run_test())

    def test_search_basic(self):
        """Test basic search functionality."""
        async def run_test():
            namespace = ("search", "test")

            await self.store.store(namespace, "build_error", "npm build failed with error")
            await self.store.store(namespace, "deploy_success", "deployment completed")
            await self.store.store(namespace, "test_failed", "unit tests failed")

            results = await self.store.search(namespace, "failed")
            self.assertEqual(len(results), 2)

            # Results should be ordered by score
            keys = [r.memory.key for r in results]
            self.assertIn("build_error", keys)
            self.assertIn("test_failed", keys)

        asyncio.run(run_test())

    def test_search_with_limit(self):
        """Test search with limit parameter."""
        async def run_test():
            namespace = ("search", "limit")

            for i in range(10):
                await self.store.store(namespace, f"item_{i}", f"test value {i}")

            results = await self.store.search(namespace, "value", limit=5)
            self.assertEqual(len(results), 5)

        asyncio.run(run_test())

    def test_list_namespaces(self):
        """Test listing namespaces."""
        async def run_test():
            await self.store.store(("project1",), "key1", "value1")
            await self.store.store(("project2",), "key2", "value2")
            await self.store.store(("project1", "sub"), "key3", "value3")

            namespaces = await self.store.list_namespaces()
            self.assertEqual(len(namespaces), 3)

        asyncio.run(run_test())

    def test_list_namespaces_with_prefix(self):
        """Test listing namespaces with prefix filter."""
        async def run_test():
            await self.store.store(("project1",), "key1", "value1")
            await self.store.store(("project2",), "key2", "value2")
            await self.store.store(("project1", "sub"), "key3", "value3")

            namespaces = await self.store.list_namespaces(prefix=("project1",))
            self.assertEqual(len(namespaces), 2)

        asyncio.run(run_test())

    def test_clear_namespace(self):
        """Test clearing a namespace."""
        async def run_test():
            namespace = ("clear", "test")

            await self.store.store(namespace, "key1", "value1")
            await self.store.store(namespace, "key2", "value2")
            await self.store.store(namespace, "key3", "value3")

            count = await self.store.clear_namespace(namespace)
            self.assertEqual(count, 3)

            keys = await self.store.list_keys(namespace)
            self.assertEqual(keys, [])

        asyncio.run(run_test())

    def test_persistence(self):
        """Test that memories persist across store instances."""
        async def run_test():
            namespace = ("persist", "test")
            key = "persist_key"
            value = "persistent_value"

            await self.store.store(namespace, key, value)

            # Create new store instance pointing to same file
            store2 = FileMemoryStore(
                file_path=os.path.join(self.test_dir, "test_memories.json")
            )

            memory = await store2.retrieve(namespace, key)
            self.assertIsNotNone(memory)
            self.assertEqual(memory.value, value)

        asyncio.run(run_test())


class TestSQLiteMemoryStore(unittest.TestCase):
    """Tests for the SQLiteMemoryStore implementation."""

    def setUp(self):
        """Create a temporary directory for test storage."""
        self.test_dir = tempfile.mkdtemp()
        self.store = SQLiteMemoryStore(
            db_path=os.path.join(self.test_dir, "test_memories.db")
        )

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_store_and_retrieve(self):
        """Test storing and retrieving a memory."""
        async def run_test():
            namespace = ("project-x", "agent-1")
            key = "test_memory"
            value = {"commit": "abc123", "duration": 45}
            metadata = {"type": "build"}

            await self.store.store(namespace, key, value, metadata)
            memory = await self.store.retrieve(namespace, key)

            self.assertIsNotNone(memory)
            self.assertEqual(memory.key, key)
            self.assertEqual(memory.value, value)
            self.assertEqual(memory.metadata, metadata)
            self.assertEqual(memory.namespace, namespace)

        asyncio.run(run_test())

    def test_retrieve_nonexistent(self):
        """Test retrieving a non-existent memory."""
        async def run_test():
            memory = await self.store.retrieve(("test",), "nonexistent")
            self.assertIsNone(memory)

        asyncio.run(run_test())

    def test_update_existing(self):
        """Test updating an existing memory (upsert behavior)."""
        async def run_test():
            namespace = ("test",)
            key = "update_test"

            await self.store.store(namespace, key, "value1")
            await self.store.store(namespace, key, "value2")

            memory = await self.store.retrieve(namespace, key)
            self.assertEqual(memory.value, "value2")

        asyncio.run(run_test())

    def test_list_keys(self):
        """Test listing keys in a namespace."""
        async def run_test():
            namespace = ("test", "keys")

            await self.store.store(namespace, "key1", "value1")
            await self.store.store(namespace, "key2", "value2")
            await self.store.store(namespace, "key3", "value3")

            keys = await self.store.list_keys(namespace)
            self.assertEqual(sorted(keys), ["key1", "key2", "key3"])

        asyncio.run(run_test())

    def test_delete(self):
        """Test deleting a memory."""
        async def run_test():
            namespace = ("test",)
            key = "delete_test"

            await self.store.store(namespace, key, "value")
            deleted = await self.store.delete(namespace, key)
            self.assertTrue(deleted)

            memory = await self.store.retrieve(namespace, key)
            self.assertIsNone(memory)

        asyncio.run(run_test())

    def test_fts5_search(self):
        """Test FTS5 full-text search."""
        async def run_test():
            namespace = ("search", "fts5")

            await self.store.store(
                namespace, "build_error",
                "The npm build failed with a compilation error in main.js"
            )
            await self.store.store(
                namespace, "deploy_success",
                "Deployment to production completed successfully"
            )
            await self.store.store(
                namespace, "test_failed",
                "Unit tests failed due to build configuration issues"
            )

            # Search for "build" should find build_error and test_failed
            results = await self.store.search(namespace, "build")
            self.assertGreaterEqual(len(results), 1)

            # Verify results contain expected keys
            keys = [r.memory.key for r in results]
            self.assertIn("build_error", keys)

        asyncio.run(run_test())

    def test_search_with_namespace_prefix(self):
        """Test search respects namespace prefix."""
        async def run_test():
            await self.store.store(("project1",), "key1", "test value one")
            await self.store.store(("project2",), "key2", "test value two")

            results = await self.store.search(("project1",), "test")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].memory.key, "key1")

        asyncio.run(run_test())

    def test_get_stats(self):
        """Test getting memory store statistics."""
        async def run_test():
            await self.store.store(("ns1",), "key1", "value1")
            await self.store.store(("ns1",), "key2", "value2")
            await self.store.store(("ns2",), "key3", "value3")

            stats = await self.store.get_stats()

            self.assertEqual(stats["total_memories"], 3)
            self.assertEqual(stats["total_namespaces"], 2)
            self.assertIn("top_namespaces", stats)
            self.assertIn("db_path", stats)

        asyncio.run(run_test())

    def test_clear_namespace(self):
        """Test clearing a namespace."""
        async def run_test():
            namespace = ("clear", "test")

            await self.store.store(namespace, "key1", "value1")
            await self.store.store(namespace, "key2", "value2")
            await self.store.store(("other",), "key3", "value3")

            count = await self.store.clear_namespace(namespace)
            self.assertEqual(count, 2)

            # Other namespace should be unaffected
            other_keys = await self.store.list_keys(("other",))
            self.assertEqual(len(other_keys), 1)

        asyncio.run(run_test())

    def test_complex_values(self):
        """Test storing and retrieving complex JSON values."""
        async def run_test():
            namespace = ("complex",)
            key = "complex_data"
            value = {
                "nested": {
                    "array": [1, 2, 3],
                    "object": {"a": "b"}
                },
                "list": ["x", "y", "z"],
                "number": 42,
                "boolean": True,
                "null": None
            }

            await self.store.store(namespace, key, value)
            memory = await self.store.retrieve(namespace, key)

            self.assertEqual(memory.value, value)

        asyncio.run(run_test())


class TestMemoryStoreFactory(unittest.TestCase):
    """Tests for the get_memory_store factory function."""

    def setUp(self):
        """Create a temporary directory for test storage."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_file_store(self):
        """Test getting a FileMemoryStore."""
        store = get_memory_store(
            "file",
            file_path=os.path.join(self.test_dir, "test.json")
        )
        self.assertIsInstance(store, FileMemoryStore)

    def test_get_sqlite_store(self):
        """Test getting a SQLiteMemoryStore."""
        store = get_memory_store(
            "sqlite",
            db_path=os.path.join(self.test_dir, "test.db")
        )
        self.assertIsInstance(store, SQLiteMemoryStore)

    def test_invalid_store_type(self):
        """Test that invalid store type raises error."""
        with self.assertRaises(ValueError):
            get_memory_store("invalid")


class TestCrossAgentScenarios(unittest.TestCase):
    """Integration tests for cross-agent memory scenarios."""

    def setUp(self):
        """Create a temporary directory for test storage."""
        self.test_dir = tempfile.mkdtemp()
        self.store = SQLiteMemoryStore(
            db_path=os.path.join(self.test_dir, "cross_agent.db")
        )

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_build_agent_shares_with_test_agent(self):
        """Test scenario: build agent shares info with test agent."""
        async def run_test():
            # Build agent stores build info
            await self.store.store(
                ("project-x", "build-agent"),
                "last_successful_build",
                {"commit": "abc123", "duration": 45, "artifacts": ["app.js", "app.css"]}
            )

            # Test agent retrieves the build info
            memory = await self.store.retrieve(
                ("project-x", "build-agent"),
                "last_successful_build"
            )

            self.assertIsNotNone(memory)
            self.assertEqual(memory.value["commit"], "abc123")

        asyncio.run(run_test())

    def test_search_across_project(self):
        """Test searching across all agents in a project."""
        async def run_test():
            # Multiple agents store different types of errors
            await self.store.store(
                ("project-x", "build-agent"),
                "error_1",
                "npm build failed: module not found",
                {"type": "build_error"}
            )
            await self.store.store(
                ("project-x", "test-agent"),
                "error_2",
                "Jest test failed: assertion error",
                {"type": "test_error"}
            )
            await self.store.store(
                ("project-x", "deploy-agent"),
                "error_3",
                "Deployment failed: connection timeout",
                {"type": "deploy_error"}
            )

            # Search for all errors in project-x
            results = await self.store.search(("project-x",), "failed")
            self.assertEqual(len(results), 3)

        asyncio.run(run_test())

    def test_namespace_isolation(self):
        """Test that different projects are isolated."""
        async def run_test():
            # Store data in two different projects
            await self.store.store(
                ("project-a",), "secret", "project-a-secret"
            )
            await self.store.store(
                ("project-b",), "secret", "project-b-secret"
            )

            # Retrieve from each project
            memory_a = await self.store.retrieve(("project-a",), "secret")
            memory_b = await self.store.retrieve(("project-b",), "secret")

            self.assertEqual(memory_a.value, "project-a-secret")
            self.assertEqual(memory_b.value, "project-b-secret")

            # Search in project-a shouldn't find project-b data
            results = await self.store.search(("project-a",), "secret")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].memory.value, "project-a-secret")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()

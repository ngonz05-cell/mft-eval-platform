"""
MFT Eval - Dataset Management

From the reference doc:
"Your eval needs realistic inputs, not toy examples."

Sources:
- Historical production data (sanitized)
- Edge cases and failure modes
- Synthetic but realistic scenarios

Dataset size guidance:
- Start with 50-100 examples for a minimum viable eval
- Scale to 500-1,000+ for production-grade evals
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Union
import csv
import json
from pathlib import Path


@dataclass
class TestCase:
    """A single test case in the dataset"""
    id: str
    input: Any
    expected_output: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "input": self.input,
            "expected_output": self.expected_output,
            **self.metadata
        }


class Dataset:
    """
    Dataset for evaluation test cases.

    Supports loading from:
    - CSV files
    - JSON files
    - Google Sheets (URL)
    - Hive tables
    - Python lists/dicts

    Example:
        # From CSV
        dataset = Dataset.from_csv("test_cases.csv")

        # From Python list
        dataset = Dataset.from_list([
            {"input": "What's my balance?", "expected": "$1,234.56"},
            {"input": "Transfer $100 to John", "expected": "Transfer initiated"},
        ])

        # From Hive (Meta internal)
        dataset = Dataset.from_hive("mft_evals.payment_extraction_v1")
    """

    def __init__(
        self,
        test_cases: List[TestCase] = None,
        name: str = "",
        version: str = "1.0.0",
        source: str = "",
    ):
        self.test_cases = test_cases or []
        self.name = name
        self.version = version
        self.source = source
        self._created_at = datetime.now()

    def __len__(self) -> int:
        return len(self.test_cases)

    def __iter__(self) -> Iterator[TestCase]:
        return iter(self.test_cases)

    def __getitem__(self, index: int) -> TestCase:
        return self.test_cases[index]

    @classmethod
    def from_csv(
        cls,
        path: str,
        input_column: str = "input",
        expected_column: str = "expected_output",
        id_column: Optional[str] = None,
    ) -> "Dataset":
        """
        Load dataset from CSV file.

        Args:
            path: Path to CSV file
            input_column: Column name for input data
            expected_column: Column name for expected output
            id_column: Column name for test case ID (optional, auto-generated if not provided)
        """
        test_cases = []

        with open(path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                test_id = row.get(id_column, f"test_{i}") if id_column else f"test_{i}"

                # Extract metadata (all columns except input/expected/id)
                metadata = {
                    k: v for k, v in row.items()
                    if k not in [input_column, expected_column, id_column]
                }

                test_cases.append(TestCase(
                    id=test_id,
                    input=row[input_column],
                    expected_output=row[expected_column],
                    metadata=metadata
                ))

        return cls(
            test_cases=test_cases,
            name=Path(path).stem,
            source=f"csv://{path}"
        )

    @classmethod
    def from_json(cls, path: str) -> "Dataset":
        """Load dataset from JSON file"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        test_cases = []
        items = data if isinstance(data, list) else data.get("test_cases", [])

        for i, item in enumerate(items):
            test_cases.append(TestCase(
                id=item.get("id", f"test_{i}"),
                input=item.get("input"),
                expected_output=item.get("expected_output", item.get("expected")),
                metadata={k: v for k, v in item.items() if k not in ["id", "input", "expected_output", "expected"]}
            ))

        return cls(
            test_cases=test_cases,
            name=Path(path).stem,
            source=f"json://{path}"
        )

    @classmethod
    def from_list(
        cls,
        items: List[Dict[str, Any]],
        input_key: str = "input",
        expected_key: str = "expected",
        name: str = "custom_dataset",
    ) -> "Dataset":
        """
        Create dataset from Python list of dicts.

        Example:
            dataset = Dataset.from_list([
                {"input": "query 1", "expected": "answer 1"},
                {"input": "query 2", "expected": "answer 2"},
            ])
        """
        test_cases = []

        for i, item in enumerate(items):
            test_cases.append(TestCase(
                id=item.get("id", f"test_{i}"),
                input=item.get(input_key),
                expected_output=item.get(expected_key),
                metadata={k: v for k, v in item.items() if k not in ["id", input_key, expected_key]}
            ))

        return cls(
            test_cases=test_cases,
            name=name,
            source="list"
        )

    @classmethod
    def from_hive(cls, table_path: str, limit: Optional[int] = None) -> "Dataset":
        """
        Load dataset from Hive table (Meta internal).

        Args:
            table_path: Full Hive table path (e.g., "mft_evals.payment_extraction_v1")
            limit: Optional row limit
        """
        # This would use Meta's internal Hive client
        # Placeholder implementation for prototyping
        try:
            # Try to import Meta's Hive client
            from daiquery import read_table

            query = f"SELECT * FROM {table_path}"
            if limit:
                query += f" LIMIT {limit}"

            df = read_table(query)
            items = df.to_dict('records')

            return cls.from_list(items, name=table_path.split('.')[-1])

        except ImportError:
            raise ImportError(
                "Hive support requires Meta internal packages. "
                "Use from_csv or from_json for local development."
            )

    @classmethod
    def from_gsheet(cls, url: str) -> "Dataset":
        """
        Load dataset from Google Sheets URL.

        Args:
            url: Google Sheets URL (must be accessible)
        """
        # This would integrate with Google Sheets API
        # Placeholder for prototyping
        raise NotImplementedError(
            "Google Sheets integration coming soon. "
            "Export to CSV and use from_csv for now."
        )

    def to_csv(self, path: str) -> None:
        """Export dataset to CSV"""
        if not self.test_cases:
            return

        # Get all unique keys from metadata
        all_keys = set()
        for tc in self.test_cases:
            all_keys.update(tc.metadata.keys())

        fieldnames = ["id", "input", "expected_output"] + sorted(all_keys)

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for tc in self.test_cases:
                writer.writerow(tc.to_dict())

    def to_json(self, path: str) -> None:
        """Export dataset to JSON"""
        data = {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "test_cases": [tc.to_dict() for tc in self.test_cases]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def sample(self, n: int, random_state: Optional[int] = None) -> "Dataset":
        """Return a random sample of test cases"""
        import random

        if random_state is not None:
            random.seed(random_state)

        sampled = random.sample(self.test_cases, min(n, len(self.test_cases)))

        return Dataset(
            test_cases=sampled,
            name=f"{self.name}_sample_{n}",
            version=self.version,
            source=self.source
        )

    def split(self, train_ratio: float = 0.7) -> tuple["Dataset", "Dataset"]:
        """Split dataset into train/test sets"""
        import random

        shuffled = self.test_cases.copy()
        random.shuffle(shuffled)

        split_idx = int(len(shuffled) * train_ratio)

        train = Dataset(
            test_cases=shuffled[:split_idx],
            name=f"{self.name}_train",
            version=self.version,
            source=self.source
        )

        test = Dataset(
            test_cases=shuffled[split_idx:],
            name=f"{self.name}_test",
            version=self.version,
            source=self.source
        )

        return train, test

    def add(self, test_case: TestCase) -> None:
        """Add a test case to the dataset"""
        self.test_cases.append(test_case)

    def filter(self, predicate) -> "Dataset":
        """Filter test cases by predicate function"""
        filtered = [tc for tc in self.test_cases if predicate(tc)]
        return Dataset(
            test_cases=filtered,
            name=f"{self.name}_filtered",
            version=self.version,
            source=self.source
        )

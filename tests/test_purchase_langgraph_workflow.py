import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.agents.purchase_team.purchase_order import supervisor_agent
from app.agents.purchase_team.purchase_order.supervisor_agent import execute
from app.model.purchase_order_intent import PurchaseOrderIntent
from app.schema.response import PurchaseOrderActionResponse


class _FakePurchaseOrderAgent:
    @staticmethod
    def execute(intent, repository):
        return PurchaseOrderActionResponse(
            status="success",
            message="Fetched purchase orders",
            data={"rows": [], "repository": repository.name},
        )


class _FakeRepository:
    name = "fake-po-repository"


class PurchaseLangGraphWorkflowTest(unittest.TestCase):
    def test_purchase_order_supervisor_invokes_langchain_tool_inside_graph(self):
        intent = PurchaseOrderIntent(action="fetch", fetchQuery="show latest purchase orders")

        with patch.dict(supervisor_agent.ACTION_TOOLS, {"fetch_agent": _FakePurchaseOrderAgent.execute}):
            response = execute(intent, _FakeRepository())

        self.assertEqual(response.status, "success")
        self.assertEqual(response.data["repository"], "fake-po-repository")
        self.assertEqual(response.data["supervisor"]["workflow"], "langgraph")
        self.assertEqual(response.data["supervisor"]["tool"], "purchase_team_purchase_order_fetch_agent")

    def test_purchase_order_supervisor_validates_before_tool_call(self):
        intent = PurchaseOrderIntent(action="close")
        close_tool = Mock(side_effect=_FakePurchaseOrderAgent.execute)

        with patch.dict(supervisor_agent.ACTION_TOOLS, {"close_agent": close_tool}):
            with self.assertRaises(HTTPException) as raised:
                execute(intent, _FakeRepository())

        close_tool.assert_not_called()
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("DocEntry is required", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()

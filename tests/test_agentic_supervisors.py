import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.agents.big_supervisor_agent import route
from app.agents.sales_team import supervisor_agent as sales_supervisor
from app.model.sales_intent import SalesIntent
from app.schema.response import SalesActionResponse


class _FakeSalesRepository:
    def table_names(self):
        return ["fake_sales_table"]


def _fake_sales_tool(intent, repository):
    return SalesActionResponse(
        status="success",
        message="Fetched sales data",
        data={"documentType": intent.documentType, "repositoryTables": repository.table_names()},
    )


class AgenticSupervisorTest(unittest.TestCase):
    def test_sales_supervisor_invokes_static_langchain_tool_registry(self):
        intent = SalesIntent(action="fetch", documentType="sales_order", fetchQuery="show sales orders")

        patched_registry = {
            **sales_supervisor.SALES_AGENT_REGISTRY,
            "sales_order": {
                "folder": "sales_order",
                "actions": {
                    **sales_supervisor.SALES_AGENT_REGISTRY["sales_order"]["actions"],
                    "fetch": ("fetch_agent", _fake_sales_tool),
                },
            },
        }
        with patch.object(sales_supervisor, "SALES_AGENT_REGISTRY", patched_registry):
            response = sales_supervisor.execute(intent, _FakeSalesRepository())

        self.assertEqual(response.status, "success")
        self.assertEqual(response.data["supervisor"]["workflow"], "langgraph")
        self.assertEqual(response.data["supervisor"]["tool"], "sales_team_sales_order_fetch_agent")

    def test_sales_supervisor_validates_before_tool_call(self):
        intent = SalesIntent(action="close", documentType="sales_order")
        close_tool = Mock(side_effect=_fake_sales_tool)
        patched_registry = {
            **sales_supervisor.SALES_AGENT_REGISTRY,
            "sales_order": {
                "folder": "sales_order",
                "actions": {
                    **sales_supervisor.SALES_AGENT_REGISTRY["sales_order"]["actions"],
                    "close": ("close_agent", close_tool),
                },
            },
        }

        with patch.object(sales_supervisor, "SALES_AGENT_REGISTRY", patched_registry):
            with self.assertRaises(HTTPException):
                sales_supervisor.execute(intent, _FakeSalesRepository())

        close_tool.assert_not_called()

    def test_big_supervisor_uses_langgraph_route_result(self):
        routed = route("show latest purchase orders")

        self.assertEqual(routed["team"], "purchase")
        self.assertEqual(routed["routing_decision"]["documentType"], "purchase_order")


if __name__ == "__main__":
    unittest.main()

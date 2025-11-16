"""
Railway auto-redeploy functionality for MercariSearcher
Copied from KufarSearcher
"""

import requests
import logging
from datetime import datetime, timedelta
from configuration_values import config
from db import get_db

logger = logging.getLogger(__name__)


class RailwayRedeployer:
    """Handles automatic redeployment on Railway"""

    def __init__(self):
        self.railway_token = config.RAILWAY_TOKEN
        self.project_id = config.RAILWAY_PROJECT_ID
        self.service_id = config.RAILWAY_SERVICE_ID
        self.db = get_db()

        self.api_url = "https://backboard.railway.app/graphql"
        self.headers = {
            "Authorization": f"Bearer {self.railway_token}",
            "Content-Type": "application/json"
        }

        self.max_errors = config.MAX_ERRORS_BEFORE_REDEPLOY

    def check_and_redeploy_if_needed(self) -> bool:
        """
        Check error count and redeploy if threshold exceeded

        Returns:
            True if redeployment was triggered
        """
        if not self._is_configured():
            logger.warning("Railway redeployment not configured")
            return False

        try:
            # Get recent critical errors
            error_count = self._get_recent_critical_errors()

            logger.info(f"Recent critical errors: {error_count}/{self.max_errors}")

            if error_count >= self.max_errors:
                logger.warning(f"Error threshold exceeded ({error_count}/{self.max_errors})")
                logger.info("Triggering Railway redeploy...")

                success = self.trigger_redeploy()

                if success:
                    logger.info("Redeploy triggered successfully")
                    self._clear_error_tracking()
                    return True
                else:
                    logger.error("Failed to trigger redeploy")
                    return False

            return False

        except Exception as e:
            logger.error(f"Error checking redeploy status: {e}")
            return False

    def _is_configured(self) -> bool:
        """Check if Railway redeploy is properly configured"""
        return all([
            self.railway_token,
            self.project_id,
            self.service_id
        ])

    def _get_recent_critical_errors(self) -> int:
        """Get count of critical errors in last hour"""
        try:
            errors = self.db.get_recent_errors(limit=100)

            # Filter for last hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_errors = [
                e for e in errors
                if datetime.fromisoformat(str(e['occurred_at']).replace('Z', '+00:00')) > one_hour_ago
            ]

            return len(recent_errors)

        except Exception as e:
            logger.error(f"Failed to get recent errors: {e}")
            return 0

    def trigger_redeploy(self) -> bool:
        """
        Trigger redeploy via Railway API

        Returns:
            True if successful
        """
        try:
            mutation = """
            mutation serviceInstanceRedeploy($serviceId: String!, $environmentId: String) {
                serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
            }
            """

            variables = {
                "serviceId": self.service_id
            }

            payload = {
                "query": mutation,
                "variables": variables
            }

            response = requests.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )

            response.raise_for_status()

            result = response.json()

            if "errors" in result:
                logger.error(f"Railway API errors: {result['errors']}")
                return False

            logger.info("Railway redeploy initiated")
            return True

        except Exception as e:
            logger.error(f"Failed to trigger redeploy: {e}")
            return False

    def _clear_error_tracking(self):
        """Clear error tracking after redeploy"""
        try:
            # Mark all errors as resolved
            if self.db.db_type == 'postgresql':
                query = "UPDATE error_tracking SET is_resolved = TRUE WHERE is_resolved = FALSE"
            else:
                query = "UPDATE error_tracking SET is_resolved = 1 WHERE is_resolved = 0"

            self.db.execute_query(query)
            logger.info("Error tracking cleared")

        except Exception as e:
            logger.error(f"Failed to clear error tracking: {e}")

    def get_deployment_status(self) -> dict:
        """
        Get current deployment status

        Returns:
            Dictionary with deployment info
        """
        try:
            query = """
            query service($id: String!) {
                service(id: $id) {
                    id
                    name
                    deployments {
                        edges {
                            node {
                                id
                                status
                                createdAt
                            }
                        }
                    }
                }
            }
            """

            variables = {
                "id": self.service_id
            }

            payload = {
                "query": query,
                "variables": variables
            }

            response = requests.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                return {"error": result["errors"]}

            return result.get("data", {})

        except Exception as e:
            logger.error(f"Failed to get deployment status: {e}")
            return {"error": str(e)}

    def get_service_info(self) -> dict:
        """Get service information"""
        try:
            query = """
            query service($id: String!) {
                service(id: $id) {
                    id
                    name
                    createdAt
                    updatedAt
                }
            }
            """

            variables = {
                "id": self.service_id
            }

            payload = {
                "query": query,
                "variables": variables
            }

            response = requests.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                return {"error": result["errors"]}

            return result.get("data", {}).get("service", {})

        except Exception as e:
            logger.error(f"Failed to get service info: {e}")
            return {"error": str(e)}


# Global instance
redeployer = None

if config.RAILWAY_TOKEN and config.RAILWAY_PROJECT_ID and config.RAILWAY_SERVICE_ID:
    redeployer = RailwayRedeployer()
    logger.info("Railway redeployer initialized")
else:
    logger.info("Railway redeployer not configured")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if redeployer:
        print("\n=== Railway Service Info ===")
        info = redeployer.get_service_info()
        print(info)

        print("\n=== Checking Redeploy Status ===")
        redeployer.check_and_redeploy_if_needed()
    else:
        print("Railway redeployer not configured")

# graphiti_manager.py

import os
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class GraphitiManager:
    """Manages the Graphiti concept mapping in Neo4j."""

    def __init__(
        self,
        uri: str = None,
        username: str = None,
        password: str = None
    ):
        """
        Initialize the Graphiti manager with Neo4j connection parameters.
        If no args provided, reads from environment:
          NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "graph_db")
        self.graphiti = None
        self.initialize()

    def initialize(self):
        """Initialize connection to Graphiti and set up indices/constraints."""
        try:
            self.graphiti = Graphiti(
                uri=self.uri,
                user=self.username,
                password=self.password
            )
            # Build any required indexes/constraints in Neo4j
            self.graphiti.build_indices_and_constraints()
            logger.info("Graphiti initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Graphiti: {e}")
            self.graphiti = None

    async def add_chat_episode(
        self,
        human_message: str,
        ai_response: str
    ) -> str | None:
        """
        Add a chat episode to the concept map.
        Returns the episode UUID, or None on failure.
        """
        if not self.graphiti:
            logger.error("Graphiti not initialized, cannot add episode")
            return None

        try:
            # Combine messages for context
            episode_body = f"Human: {human_message}\n\nAI: {ai_response}"
            episode_name = f"Chat Episode {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            result = await self.graphiti.add_episode(
                name=episode_name,
                episode_body=episode_body,
                source=EpisodeType.text,
                source_description="chat_interaction",
                reference_time=datetime.now(timezone.utc)
            )
            # Extract a stable identifier
            try:
                episode_uuid = result.uuid
            except AttributeError:
                episode_uuid = str(result)
            logger.info(f"Added chat episode with UUID: {episode_uuid}")
            return episode_uuid

        except Exception as e:
            logger.error(f"Error adding chat episode: {e}")
            return None

    async def search_knowledge_graph(
        self,
        query: str,
        center_node_uuid: str | None = None
    ) -> list:
        """
        Search the knowledge graph for relevant information.
        If center_node_uuid given, will rerank by graph distance.
        Returns a list of result objects.
        """
        if not self.graphiti:
            logger.error("Graphiti not initialized, cannot search")
            return []

        try:
            if center_node_uuid:
                results = await self.graphiti.search(query, center_node_uuid)
            else:
                results = await self.graphiti.search(query)
            return results

        except Exception as e:
            logger.error(f"Error searching Graphiti knowledge graph: {e}")
            return []

    def close(self):
        """Close the Neo4j connection."""
        if self.graphiti:
            try:
                self.graphiti.close()
                logger.info("Graphiti connection closed")
            except Exception as e:
                logger.error(f"Error closing Graphiti connection: {e}")

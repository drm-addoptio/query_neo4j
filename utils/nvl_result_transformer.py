# Import the recordMapper and recordCollector functions
from utils.record_mapper import record_mapper_parallel  # Adjust the import path as needed
from utils.record_collector import record_collector  # Adjust the import path as needed

def nvl_result_transformer(records, element_limit=1000):
    """
    Transform Neo4j query results into a graph representation with a limit on the total number of elements.
    """
    graph_elements = []
    total_elements = 0

    # Iterate over each record and extract nodes and relationships
    for record in records:
        if total_elements >= element_limit:
            break  # Stop processing once the limit is reached

        # Use the record_mapper_parallel to get nodes and relationships
        elements = record_mapper_parallel(record)

        # Calculate the remaining capacity for elements
        remaining_capacity = element_limit - total_elements

        # Append only up to the remaining capacity
        if len(elements) > remaining_capacity:
            graph_elements.extend(elements[:remaining_capacity])
            total_elements += remaining_capacity
        else:
            graph_elements.extend(elements)
            total_elements += len(elements)
    
    # Collect nodes and relationships using the collector function
    collected_data = record_collector(graph_elements)
    # Ensure that the result data is in the correct format for NVL
    nodes = collected_data["nodes"]
    relationships = collected_data["relationships"]


    # Return the nodes and relationships as expected by NVL
    return {
        "nodes": nodes,
        "relationships": relationships
    }

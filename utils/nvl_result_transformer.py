# Import the recordMapper and recordCollector functions
from utils.record_mapper import record_mapper  # Adjust the import path as needed
from utils.record_collector import record_collector  # Adjust the import path as needed

def nvl_result_transformer(records):
    graph_elements = []

    # Iterate over each record and extract nodes and relationships
    for record in records:
        # Use the record_mapper to get nodes and relationships
        elements = record_mapper(record)
        graph_elements.append(elements)


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

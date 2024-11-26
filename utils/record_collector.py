def record_collector(graph_elements):
    nodes = []
    relationships = []
    for element in graph_elements:
        # Check if the element is a Node
        if element.get("type") == "node":
            nodes.append(element)  # Keep node's existing properties

        # Check if the element is a Relationship
        elif element.get("type") == "relationship":
            relationships.append(element)  # Keep relationship's existing properties

    return {
        "nodes": nodes,
        "relationships": relationships
    }

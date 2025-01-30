def record_collector(graph_elements):
    nodes = []
    relationships = []
    
    for element in graph_elements:
        element_type = element.get("type")

        if element_type == "node":
            nodes.append(element)

        elif element_type == "relationship":
            relationships.append(element)

        elif element_type == "path":
            nodes.extend(element["nodes"])
            relationships.extend(element["relationships"])

    return {
        "nodes": nodes,
        "relationships": relationships
    }

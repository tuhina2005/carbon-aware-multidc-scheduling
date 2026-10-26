#include <data_structure/dag.hpp>

DAG::DAG(const std::string& filename) {
  count_Nodes_Edges(filename); 
  readGraph(filename); 
}

void DAG::count_Nodes_Edges(const std::string& filename) {
  std::ifstream file(filename);
  if (!file.is_open()) {
    throw std::runtime_error("Could not open the DAG file for counting");
  }
  std::string line;
  numNodes = 0; 
  numEdges = 0;
  while (std::getline(file, line)) {
    std::istringstream iss(line);
    std::string token;
    // Node line
    if (line.find("[weight=") != std::string::npos) {
      numNodes++;
    }

    // Edge line
    if (line.find("->") != std::string::npos) {
      numEdges++;
    }
  }

  nodeWeights.resize(numNodes);
  adjList_inNeighbors.resize(numNodes);
  adjList_outNeighbors.resize(numNodes);

  file.close();
}

void DAG::readGraph(const std::string& filename) {
  std::ifstream file(filename); 
  if (!file.is_open()) {
    throw std::invalid_argument("Could not open the DAG file for reading");
  }

  std::string line;
  while (std::getline(file, line)) {
    std::stringstream ss(line);
    std::string token; 

    if (line.find("[weight=") != std::string::npos) {
      // Node line
      std::string node; 
      ss >> node >> token; 
      int nodeID = std::stoi(node);
      int nodeWeight = -1; 
      std::regex num_regex(R"(\d+)"); 
      std::smatch match; 
      if (std::regex_search(token, match, num_regex)) {
        nodeWeight = std::stoi(match.str()); 
      } else {
        throw::std::runtime_error("No weight specified for the vertex!"); 
      }
      nodeWeights[nodeID] = nodeWeight; 
    } else if (line.find("->") != std::string::npos) {
      std::string from, to; 
      ss >> from >> token >> to >> token;
      int sourceID = std::stoi(from);
      int targetID = std::stoi(to);
      int edgeWeight = -1; 
      std::regex num_regex(R"(\d+)"); 
      std::smatch match; 
      if (std::regex_search(token, match, num_regex)) {
        edgeWeight = std::stoi(match.str()); 
      } else {
        throw::std::runtime_error("No weight specified for the vertex!"); 
      }
        vertex v_out = {targetID, edgeWeight, "comp", std::make_pair(-1, -1)};
        vertex v_in = {sourceID, edgeWeight, "comp", std::make_pair(-1, -1)};
        adjList_outNeighbors[sourceID].push_back(v_out);
        adjList_inNeighbors[targetID].push_back(v_in);
    }
  }
  file.close();
}

void DAG::printGraph() const {
  std::cout << "==================================" << std::endl;
  std::cout << "            PRINT DAG             " << std::endl; 
  std::cout << "==================================" << std::endl;
  std::cout << "Number of nodes: " << numNodes << ". Number of edges: " << numEdges << std::endl;
  std::cout << "Node weights: " << std::endl;
  for (size_t i = 0; i < nodeWeights.size(); i++) {
    std::cout << "Node " << i << ": " << nodeWeights[i] << std::endl;
  }

  std::cout << "Adjacency list (out): " << std::endl;
  for (size_t i = 0; i < numNodes; i++) {
    std::cout << i << ": ";
    for (size_t j = 0; j < adjList_outNeighbors[i].size(); j++) {
      std::cout << adjList_outNeighbors[i][j].id << " "; 
    }
    std::cout << std::endl; 
  }

  std::cout << "Adjacency list (in): " << std::endl;
  for (size_t i = 0; i < numNodes; i++) {
    for (size_t j = 0; j < adjList_inNeighbors[i].size(); j++) {
      std::cout << adjList_inNeighbors[i][j].id << " "; 
    }
    std::cout << std::endl; 
  }
}

unsigned int DAG::getEdgeWeight(unsigned int from, unsigned int to) const {
  for (const auto& neighbor : adjList_outNeighbors[from]) {
    if (neighbor.id == to) {
      return neighbor.weight;
    }
  }
  throw std::invalid_argument("Edge does not exist");
}

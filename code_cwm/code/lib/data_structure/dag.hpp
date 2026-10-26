#pragma once

#include <unordered_map>
#include <queue>
#include <vector>
#include <functional>
#include <iostream>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <unordered_set>
#include <string>
#include <algorithm>
#include <set>
#include <regex>
#include <iterator>
#include <optional>
#include <tools/common.hpp>

/*!
* Data structure used to store the input workflow 
*/
class DAG {
  public: 
    DAG() = default;
    DAG(const std::string& filename); 

    void readGraph(const std::string& filename); 

    void count_Nodes_Edges(const std::string& filename); 

    void printGraph() const;

    unsigned int getNumNodes() const {
      return numNodes;
    }

    unsigned int getNumEdges() const {
      return numEdges;
    }

    unsigned int getEdgeWeight(unsigned int from, unsigned int to) const;

    friend struct vertex;

  //private:
    std::vector<std::vector<vertex>> adjList_inNeighbors;
    std::vector<std::vector<vertex>> adjList_outNeighbors; 
    std::vector<int> nodeWeights;

    unsigned int numNodes = 0; 
    unsigned int numEdges = 0; 
};
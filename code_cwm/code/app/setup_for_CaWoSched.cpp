#include <iostream>
#include <filesystem>
#include <algorithms/mapper.hpp>
#include <config.hpp>

int main(int argc, char** argv) {

  if (argc != 7) {
    std::cout << "Required arguments: \n";
    std::cout << "  <DAG file> \n";
    std::cout << "  Cluster configuration file \n";
    std::cout << "  Cluster variant <small> or <large> \n";
    std::cout << "  Profile configuration file \n";
    std::cout << "  Random seed for tie breaking \n";
    std::cout << "  Flexibility factor (e.g., 1.2 for 20%) \n";
    return 1; 
  }

  std::filesystem::path const graphPath(std::move(argv[1])); 
  std::filesystem::path const clusterPath(std::move(argv[2]));
  std::string const clusterVariant(std::move(argv[3]));
  std::filesystem::path const profilePath(std::move(argv[4]));
  unsigned int seed = std::stoi(argv[5]);
  unsigned int deadline = std::stoi(argv[6]);

  CaWoMap Mapper(graphPath.c_str(), clusterPath.c_str(), clusterVariant.c_str(), profilePath.c_str(), seed); 

 
  Mapper.printSetupForCaWoSched(deadline);


  return 0;
}
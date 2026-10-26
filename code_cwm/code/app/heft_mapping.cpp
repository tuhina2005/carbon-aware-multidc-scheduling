#include <iostream>
#include <filesystem>
#include <algorithms/mapper.hpp>
#include <config.hpp>

int main(int argc, char** argv) {

  if (argc != 5) {
    std::cout << "Required arguments: \n";
    std::cout << "  <DAG file> \n";
    std::cout << "  Cluster configuration file \n";
    std::cout << "  Cluster variant <small> or <large> \n";
    std::cout << "  Profile configuration file \n";
    return 1; 
  }

  std::filesystem::path const graphPath(std::move(argv[1])); 
  std::filesystem::path const clusterPath(std::move(argv[2]));
  std::string const clusterVariant(std::move(argv[3]));
  std::filesystem::path const profilePath(std::move(argv[4]));
  unsigned int seed = 42;

  CaWoMap Mapper(graphPath.c_str(), clusterPath.c_str(), clusterVariant.c_str(), profilePath.c_str(), seed); 
  Mapper.prepare_HEFT();
  Schedule HEFT_Result = Mapper.HEFT();
  if (Mapper.HEFT_correctness()) {
    Mapper.printMappingForCaWoSched();
    std::cout << HEFT_Result.makespan << std::endl;
  } else {
    std::cout << "HEFT Mapping is NOT valid!\n";
    return 1;
  }

  return 0;
}
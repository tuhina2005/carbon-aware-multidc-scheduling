#include <iostream>
#include <filesystem>
#include <algorithms/mapper.hpp>
#include <config.hpp>
#include <tools/common.hpp>
#include <chrono>

int main(int argc, char** argv) {

  if (argc != 6) {
    std::cout << "Required arguments: \n";
    std::cout << "  <DAG file> \n";
    std::cout << "  Cluster configuration file \n";
    std::cout << "  Cluster variant <small> or <large> \n";
    std::cout << "  Profile configuration file \n";
    std::cout << "  variant \n";
    return 1; 
  }

  std::filesystem::path const graphPath(std::move(argv[1])); 
  std::filesystem::path const clusterPath(std::move(argv[2]));
  std::string const clusterVariant(std::move(argv[3]));
  std::filesystem::path const profilePath(std::move(argv[4]));
  std::string const CWM_variant(std::move(argv[5]));
  unsigned int seed = 42; 

  unsigned int tight_deadline = UINT_MAX;
  
  {
    CaWoMap heftOnly(graphPath.c_str(), clusterPath.c_str(), clusterVariant.c_str(), profilePath.c_str(), seed);
    
    auto start = std::chrono::high_resolution_clock::now();
    heftOnly.prepare_HEFT();
    Schedule heftSchedule = heftOnly.HEFT();
    auto end = std::chrono::high_resolution_clock::now();
    auto diff = std::chrono::duration_cast<std::chrono::milliseconds>(end-start);
    
    unsigned int heft_CC = heftOnly.HEFT_compute_carbon_cost_fast();
    tight_deadline = heftSchedule.makespan;
    
    bool is_correct = heftOnly.HEFT_correctness();
    if (!is_correct) {
      std::cout << "HEFT Mapping is NOT valid!\n";
      return 1;
    }
    std::cout << "Algorithm,time[ms],makespan,deadline,carbon cost,validity,factor\n";
    std::cout << "HEFT-SL," << diff.count() << "," << heftSchedule.makespan << "," << heftSchedule.makespan << "," << heft_CC << "," << is_correct << ",1.0" << std::endl;
  }
  
  
  // Now compute CWM with flexibility factor 1.2
  
  {
    unsigned int deadline = static_cast<unsigned int>(std::ceil(1.2 * tight_deadline));
    CaWoMap CWM(graphPath.c_str(), clusterPath.c_str(), clusterVariant.c_str(), profilePath.c_str(), seed);
    auto startCWM = std::chrono::high_resolution_clock::now();
    CWM.prepare_HEFT();
    Schedule CWMschedule = CWM.CaWoMap_Init(CWM_variant);
    CWM.guarantee_deadline_routine(CWMschedule, deadline);
    auto endCWM = std::chrono::high_resolution_clock::now();
    auto diffCWM = std::chrono::duration_cast<std::chrono::milliseconds>(endCWM-startCWM);
    bool is_CWM_correct = CWM.final_correctness();
    if (!is_CWM_correct) {
      std::cout << "CWM schedule is NOT valid!\n";
      return 1;
    }
    Schedule& S = CWM.get_final_schedule();
    S.carbonCost = CWM.final_compute_carbon_cost_fast();
    S.makespan = CWM.compute_final_makespan();
    std::cout << "CWM," << diffCWM.count() << "," << S.makespan << "," << deadline << "," << S.carbonCost << "," << is_CWM_correct << ",1.2" << std::endl;
  }

  // Now compute CWM with flexibility factor 1.5
  {
    unsigned int deadline = static_cast<unsigned int>(std::ceil(1.5 * tight_deadline));
    CaWoMap CWM(graphPath.c_str(), clusterPath.c_str(), clusterVariant.c_str(), profilePath.c_str(), seed);
    auto startCWM = std::chrono::high_resolution_clock::now();
    CWM.prepare_HEFT();
    Schedule CWMschedule = CWM.CaWoMap_Init(CWM_variant);
    CWM.guarantee_deadline_routine(CWMschedule, deadline);
    auto endCWM = std::chrono::high_resolution_clock::now();
    auto diffCWM = std::chrono::duration_cast<std::chrono::milliseconds>(endCWM-startCWM);
    bool is_CWM_correct = CWM.final_correctness();
    if (!is_CWM_correct) {
      std::cout << "CWM schedule is NOT valid!\n";
      return 1;
    }
    Schedule& S = CWM.get_final_schedule();
    S.carbonCost = CWM.final_compute_carbon_cost_fast();
    S.makespan = CWM.compute_final_makespan();
    std::cout << "CWM," << diffCWM.count() << "," << S.makespan << "," << deadline << "," << S.carbonCost << "," << is_CWM_correct << ",1.5" << std::endl;
  }

  // Now compute CWM with flexibility factor 2.0
  {
    unsigned int deadline = static_cast<unsigned int>(std::ceil(2.0 * tight_deadline));
    CaWoMap CWM(graphPath.c_str(), clusterPath.c_str(), clusterVariant.c_str(), profilePath.c_str(), seed);
    auto startCWM = std::chrono::high_resolution_clock::now();
    CWM.prepare_HEFT();
    Schedule CWMschedule = CWM.CaWoMap_Init(CWM_variant);
    CWM.guarantee_deadline_routine(CWMschedule, deadline);
    auto endCWM = std::chrono::high_resolution_clock::now();
    auto diffCWM = std::chrono::duration_cast<std::chrono::milliseconds>(endCWM-startCWM);
    bool is_CWM_correct = CWM.final_correctness();
    if (!is_CWM_correct) {
      std::cout << "CWM schedule is NOT valid!\n";
      return 1;
    }
    Schedule& S = CWM.get_final_schedule();
    S.carbonCost = CWM.final_compute_carbon_cost_fast();
    S.makespan = CWM.compute_final_makespan();
    std::cout << "CWM," << diffCWM.count() << "," << S.makespan << "," << deadline << "," << S.carbonCost << "," << is_CWM_correct << ",2.0" << std::endl;
  }

  return 0;
}
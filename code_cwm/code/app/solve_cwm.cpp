#include <iostream>
#include <filesystem>
#include <string>
#include <chrono>
#include <cstdint>
#include <climits>
#include <stdexcept>
#include <algorithms/mapper.hpp>
#include <config.hpp>
#include <tools/common.hpp>

int main(int argc, char** argv) {
  if (argc != 7) {
    std::cerr << "Usage: " << argv[0] << " <DAG> <cluster.json> <small|large> <profile.json> <deadline> <seed>\n";
    std::cerr << "  <DAG>           Path to DAG workflow .dot file\n";
    std::cerr << "  <cluster.json>  Path to cluster configuration JSON file\n";
    std::cerr << "  <small|large>   Cluster variant ('small' or 'large')\n";
    std::cerr << "  <profile.json>  Path to power profile JSON file\n";
    std::cerr << "  <deadline>      Global makespan deadline (positive integer)\n";
    std::cerr << "  <seed>          Random seed for tie-breaking (unsigned integer)\n";
    return 1;
  }

  std::filesystem::path const dagPath(argv[1]);
  std::filesystem::path const clusterPath(argv[2]);
  std::string const clusterVariant(argv[3]);
  std::filesystem::path const profilePath(argv[4]);
  std::string const deadlineStr(argv[5]);
  std::string const seedStr(argv[6]);

  // Validate file existence
  if (!std::filesystem::exists(dagPath)) {
    std::cerr << "Error: DAG file does not exist: " << dagPath << "\n";
    return 1;
  }
  if (!std::filesystem::exists(clusterPath)) {
    std::cerr << "Error: Cluster configuration file does not exist: " << clusterPath << "\n";
    return 1;
  }
  if (clusterVariant != "small" && clusterVariant != "large") {
    std::cerr << "Error: Cluster variant must be either 'small' or 'large', got: " << clusterVariant << "\n";
    return 1;
  }
  if (!std::filesystem::exists(profilePath)) {
    std::cerr << "Error: Profile file does not exist: " << profilePath << "\n";
    return 1;
  }

  // Validate and parse deadline
  unsigned int deadline = 0;
  try {
    size_t idx = 0;
    unsigned long val = std::stoul(deadlineStr, &idx);
    if (idx != deadlineStr.size() || val == 0 || val > UINT_MAX) {
      throw std::out_of_range("Invalid deadline value");
    }
    deadline = static_cast<unsigned int>(val);
  } catch (const std::exception& e) {
    std::cerr << "Error: Deadline must be a positive integer within uint32 range, got: " << deadlineStr << "\n";
    return 1;
  }

  // Validate and parse seed
  unsigned int seed = 0;
  try {
    size_t idx = 0;
    unsigned long val = std::stoul(seedStr, &idx);
    if (idx != seedStr.size() || val > UINT_MAX) {
      throw std::out_of_range("Invalid seed value");
    }
    seed = static_cast<unsigned int>(val);
  } catch (const std::exception& e) {
    std::cerr << "Error: Seed must be an unsigned integer within uint32 range, got: " << seedStr << "\n";
    return 1;
  }

  try {
    std::cerr << "[DEBUG] Constructing CaWoMap with seed=" << seed << " deadline=" << deadline << "\n";
    CaWoMap CWM(dagPath.string(), clusterPath.string(), clusterVariant, profilePath.string(), seed);

    std::cerr << "[DEBUG] Calling prepare_HEFT()...\n";
    auto start = std::chrono::high_resolution_clock::now();
    CWM.prepare_HEFT();

    std::cerr << "[DEBUG] Calling CaWoMap_Init('local-search')...\n";
    Schedule cwmSchedule = CWM.CaWoMap_Init("local-search");

    std::cerr << "[DEBUG] Calling guarantee_deadline_routine()...\n";
    CWM.guarantee_deadline_routine(cwmSchedule, deadline);
    auto end = std::chrono::high_resolution_clock::now();
    auto elapsedMs = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    std::cerr << "[DEBUG] Calling final_correctness()...\n";
    if (!CWM.final_correctness()) {
      std::cerr << "Error: Generated CWM schedule failed correctness verification.\n";
      return 1;
    }

    std::cerr << "[DEBUG] Computing final carbon and makespan...\n";
    Schedule& finalSched = CWM.get_final_schedule();
    finalSched.carbonCost = CWM.final_compute_carbon_cost_fast();
    finalSched.makespan = CWM.compute_final_makespan();

    if (finalSched.makespan > deadline) {
      std::cerr << "Error: Schedule makespan (" << finalSched.makespan
                << ") exceeds deadline (" << deadline << ").\n";
      return 1;
    }

    // Output format requirement: exactly one CSV line containing execution time, makespan, carbon cost
    std::cout << elapsedMs << "," << finalSched.makespan << "," << finalSched.carbonCost << "\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "Error during CWM execution: " << e.what() << "\n";
    return 1;
  }
}

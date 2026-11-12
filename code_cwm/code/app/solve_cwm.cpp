#include <iostream>
#include <filesystem>
#include <string>
#include <chrono>
#include <cstdint>
#include <climits>
#include <numeric>
#include <vector>
#include <stdexcept>
#include <algorithms/mapper.hpp>
#include <config.hpp>
#include <tools/common.hpp>

int main(int argc, char** argv) {
  // Optional 7th argument "--per-interval" (multi-DC extension). Without it the
  // output is exactly the baseline single CSV line.
  // Optional trailing flags (multi-DC extension), in any order:
  //   --per-interval : print a second line with per-interval excess energy and a third
  //                    line with per-interval TOTAL energy (both 64 bit)
  //   --heft         : evaluate the plain HEFT schedule instead of CWM (baseline B2)
  bool perInterval = false;
  bool heftOnly = false;
  while (argc > 7) {
    std::string const flag(argv[argc - 1]);
    if (flag == "--per-interval") perInterval = true;
    else if (flag == "--heft") heftOnly = true;
    else break;
    --argc;
  }
  if (argc != 7) {
    std::cerr << "Usage: " << argv[0] << " <DAG> <cluster.json> <small|large> <profile.json> <deadline> <seed> [--per-interval] [--heft]\n";
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

  if (heftOnly) {
    try {
      CaWoMap H(dagPath.string(), clusterPath.string(), clusterVariant, profilePath.string(), seed);
      auto start = std::chrono::high_resolution_clock::now();
      H.prepare_HEFT();
      Schedule heftSched = H.HEFT();
      auto end = std::chrono::high_resolution_clock::now();
      auto elapsedMs = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
      if (!H.HEFT_correctness()) {
        std::cerr << "Error: HEFT schedule failed correctness verification.\n";
        return 1;
      }
      if (heftSched.makespan > deadline) {
        std::cerr << "Error: Schedule makespan (" << heftSched.makespan
                  << ") exceeds deadline (" << deadline << ").\n";
        return 1;
      }
      std::vector<unsigned long long> energy;
      std::vector<unsigned long long> perInt = H.HEFT_carbon_cost_per_interval(&energy);
      unsigned long long total = std::accumulate(perInt.begin(), perInt.end(), 0ULL);
      std::cout << elapsedMs << "," << heftSched.makespan << "," << total << "\n";
      if (perInterval) {
        for (size_t i = 0; i < perInt.size(); ++i) std::cout << (i ? "," : "") << perInt[i];
        std::cout << "\n";
        for (size_t i = 0; i < energy.size(); ++i) std::cout << (i ? "," : "") << energy[i];
        std::cout << "\n";
      }
      return 0;
    } catch (const std::exception& e) {
      std::cerr << "Error during HEFT execution: " << e.what() << "\n";
      return 1;
    }
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
    if (!perInterval) {
      std::cout << elapsedMs << "," << finalSched.makespan << "," << finalSched.carbonCost << "\n";
    } else {
      // Line 1: elapsed_ms,makespan,carbon_cost (64-bit, overflow-safe sum)
      // Line 2: per-interval excess energy for each profile interval, comma-separated
      std::vector<unsigned long long> energy;
      std::vector<unsigned long long> perInt = CWM.final_carbon_cost_per_interval(&energy);
      unsigned long long total = std::accumulate(perInt.begin(), perInt.end(), 0ULL);
      std::cout << elapsedMs << "," << finalSched.makespan << "," << total << "\n";
      for (size_t i = 0; i < perInt.size(); ++i) {
        std::cout << (i ? "," : "") << perInt[i];
      }
      std::cout << "\n";
      // Line 3: per-interval total energy (idle + work), integral of P(t)
      for (size_t i = 0; i < energy.size(); ++i) {
        std::cout << (i ? "," : "") << energy[i];
      }
      std::cout << "\n";
    }
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "Error during CWM execution: " << e.what() << "\n";
    return 1;
  }
}

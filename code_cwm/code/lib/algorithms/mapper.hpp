#pragma once

#include <unordered_map>
#include <map>
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
#include <iterator>
#include <optional>
#include <data_structure/dag.hpp>
#include <config.hpp>
#include <tuple>
#include <tools/common.hpp>
#include <iomanip>
#include <bitset>

//using namespace CaWoMap;
#include <random>
#include <string>

class CoinFlipper {
public:
    explicit CoinFlipper(unsigned int seed)
        : rng(seed), dist(0, 1) {}

    bool flip() {
        return dist(rng) == 1;
    }

private:
    std::mt19937 rng;      
    std::uniform_int_distribution<int> dist;
};

class CaWoMap {
  public:
    CaWoMap(const std::string& DAGFile, const std::string& clusterFile, const std::string& clusterVariant, const std::string& profilePath, unsigned int seed, unsigned int deadline) : G(DAGFile), flipper(seed) {
      _config.setDAGFile(DAGFile);
      _config.setClusterSetupFileAndVariant(clusterFile, clusterVariant);
      _config.setProfileFile(profilePath);
      _config.parseProfile();
      _config.parseClusterSetup();
      _config.setBasePower();
      _config.setRandomSeed(seed);
      _config.seedRNG(seed);
      _config.setDeadline(deadline);
      all_processor_subsets.resize((_config.getIntervals().size() - 1)); 
      for (unsigned int i = 0; i < _config.getIntervals().size() - 1; ++i) {
        interval_map[_config.getIntervals()[i]] = {_config.getIntervals()[i+1], i};
      }
    } 

    /*!
    * This constructor is used when we want to compute the HEFT mapping only (no profile, no deadline).
    */
    CaWoMap(const std::string& DAGFile, const std::string& clusterFile, const std::string& clusterVariant, const std::string& profilePath, unsigned int seed) : G(DAGFile), flipper(seed) {
      _config.setDAGFile(DAGFile);
      _config.setClusterSetupFileAndVariant(clusterFile, clusterVariant);
      _config.setProfileFile(profilePath);
      _config.parseProfile();
      _config.parseClusterSetup();
      _config.setBasePower();
      _config.setRandomSeed(seed);
      _config.seedRNG(seed);
      for (unsigned int i = 0; i < _config.getIntervals().size() - 1; ++i) {
        interval_map[_config.getIntervals()[i]] = {_config.getIntervals()[i+1], i};
      }
    
    }

    void printDAG(); 

    void compute_topological_order(std::vector<unsigned int>& topological_order);

    void compute_upward_ranks(std::vector<float>& upward_rank, std::vector<unsigned int>& topological_order);

    void compute_avg_comp_cost(std::vector<float>& avg_comp_cost);

    unsigned int get_running_time(unsigned int task, PE P);

    /*!
    * For every interval choose the subset of the PEs that can work concurrently without using brown power.
    */
    std::vector<PE> compute_processor_subset(const budget powerBudget, double offset = 0.0);

    void print_result() const { result.print(); }

    Schedule HEFT();

    // For comparison with CaWoSched:
    void printMappingForCaWoSched();

    void printSetupForCaWoSched(unsigned int deadline);

    void prepare_HEFT();

    bool HEFT_correctness();
    
    bool CWM_correctness();

    /*!
    * compute all processor subsets for each interval
    */
    void prepare_processor_subsets(double offset = 0.0); 

    unsigned int getIntervalId(unsigned int time);

    Schedule CaWoMap_Init(const std::string& variant = "default");
    
    unsigned int compute_EST_without_communications(unsigned int task);

    unsigned int HEFT_compute_carbon_cost_fast();

    unsigned int CWM_compute_carbon_cost_fast();

    unsigned int covers_how_many(unsigned int start, unsigned int end);

    void guarantee_deadline(const unsigned int threshold);
    
    void guarantee_deadline_routine(Schedule& S, const unsigned int deadline);

    unsigned int final_compute_carbon_cost_fast();

    Schedule& get_final_schedule() { return final_schedule; }

    unsigned int compute_final_makespan();

    void include_later_tasks_in_interval(
      unsigned int task_to_reschedule,
      unsigned int interval_end,
      std::vector<unsigned int>& later_tasks
    );

    void prevent_overlaps_in_later_tasks(const unsigned int task_to_move, std::vector<unsigned int>& later_tasks);

    void prevent_overlaps_in_channels(std::vector<std::pair<uint64_t, Transfer_details>>& affected_messages);
    
    void include_later_tasks_in_interval_final(
      unsigned int task_to_reschedule,
      unsigned int interval_end,
      std::vector<unsigned int>& later_tasks
    );

    void prevent_overlaps_in_later_tasks_final(const unsigned int task_to_move, std::vector<unsigned int>& later_tasks);

    void prevent_overlaps_in_channels_final(std::vector<std::pair<uint64_t, Transfer_details>>& affected_messages);
    /*
    * If 'not_earlier_than' is given the tasks can start at not_earlier_than the earliest
    */
    void find_choice(
      const unsigned int& task,
      choice& bestChoice,
      Job& current_job, 
      std::vector<unsigned int>& arrivals,
      std::vector<Transfer>& transfers,
      std::vector<PE>& current_PE_subset,
      unsigned int not_earlier_than = 0
    );

    bool local_search(unsigned int deadline = 0);
    void local_search_routine(unsigned int& makespan, unsigned int deadline = 0);
    
    bool local_search_final(unsigned int deadline = 0);
    void local_search_routine_final(unsigned int& makespan, unsigned int deadline = 0);
    bool final_correctness();

    void include_successors_DFS(unsigned int task, std::vector<bool>& is_included);

  private:
    DAG G; 
    std::vector<unsigned int> processor_of_task;
    std::vector<std::pair<unsigned int, unsigned int>> start_and_end_times; // start and end times of tasks, start is inclusive, end is exclusive. 
    SchedulerConfig _config;

    std::vector<IntervalSet> links;
    std::vector<IntervalSet> processors;
    std::vector<IntervalSet> CWM_links;
    std::vector<IntervalSet> CWM_processors;

    std::vector<unsigned int> heft_processor_of_task;
    std::vector<std::pair<unsigned int, unsigned int>> heft_start_and_end_times;

    output result;
    
    std::vector<std::vector<PE>> all_processor_subsets; // all subsets of processors for each interval

    // 16 bits suffice here
    std::vector<std::vector<uint16_t>> running_times;

    Schedule HEFT_schedule;
    Schedule CWM_schedule;
    Schedule final_schedule;

    std::map<unsigned int, Endpoint> interval_map;

    std::vector<IntervalSet> final_links;
    std::vector<IntervalSet> final_processors;

    std::vector<std::pair<unsigned int, unsigned int>> final_start_and_end_times;
    std::vector<unsigned int> final_processor_of_task;

    CoinFlipper flipper;
};
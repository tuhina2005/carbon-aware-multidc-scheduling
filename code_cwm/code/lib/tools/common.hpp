/*
* Common data structures and type definitions for the scheduler
*/

#pragma once

#include <string>
#include <utility>
#include <unordered_map>
#include <map>

// For the updatable priority queue
#include <set>
#include <random>
#include <climits>

// For the dynamic vector 
#include <vector>
#include <algorithm>
#include <concepts>

#include <robin_hood.h>


//namespace CaWoMap {

using Task = unsigned int;
using PE = unsigned int;
using budget = unsigned int;
using power = unsigned int;

struct Transfer {
  unsigned int link_id;
  unsigned int start_time;
  unsigned int end_time;
  uint64_t id;
};

struct choice {
  unsigned int bestStart;
  unsigned int bestFinish;
  unsigned int bestProc;
  std::vector<Transfer> bestTransfers;
};

/*!
* Stores a vertex but weight is the corresponding edge weight for storing the vertex in the adjacency list.
* In case it is a communication vertex, we store the original edge
*/
struct vertex {
  unsigned int id;
  unsigned int weight;
  std::string type; // "comp" or "comm"
  std::pair<int, int> comm_id; // = -1,-1 if type = comp


  vertex() = default;
  vertex(int id_, int weight_, std::string type_, std::pair<int, int> comm_id_) : id(id_), weight(weight_), type(type_), comm_id(comm_id_) {}
}; 

struct Endpoint {
  unsigned int interval_end;
  unsigned int interval_id;
};

struct EndpointWithBudget {
  unsigned int interval_end;
  unsigned int interval_id;
  unsigned int budget;
};

struct interval_with_budget_and_id {
  unsigned int start;
  unsigned int end;
  unsigned int budget;
  unsigned int id;
  unsigned int power;
};

struct output {
  unsigned int HEFT_makespan;
  unsigned int deadline_levelOne;
  unsigned int deadline_levelTwo;
  unsigned int deadline_levelThree;
  unsigned int makespan_levelOne;
  unsigned int makespan_levelTwo;
  unsigned int makespan_levelThree;
  unsigned int HEFT_carbon_cost;
  unsigned int carbon_cost_levelOne;
  unsigned int carbon_cost_levelTwo;
  unsigned int carbon_cost_levelThree;
  double time_HEFT;
  double time_deadlineAgnosticMapping_levelOne;
  double time_deadlineAgnosticMapping_levelTwo;
  double time_deadlineAgnosticMapping_levelThree;
  double time_repairRoutine_levelOne;
  double time_repairRoutine_levelTwo;
  double time_repairRoutine_levelThree;


  output() : HEFT_makespan(UINT_MAX), deadline_levelOne(UINT_MAX), deadline_levelTwo(UINT_MAX), deadline_levelThree(UINT_MAX), makespan_levelOne(UINT_MAX), makespan_levelTwo(UINT_MAX), makespan_levelThree(UINT_MAX), HEFT_carbon_cost(UINT_MAX), carbon_cost_levelOne(UINT_MAX), carbon_cost_levelTwo(UINT_MAX), carbon_cost_levelThree(UINT_MAX), time_HEFT(0), time_deadlineAgnosticMapping_levelOne(0), time_deadlineAgnosticMapping_levelTwo(0), time_deadlineAgnosticMapping_levelThree(0), time_repairRoutine_levelOne(0), time_repairRoutine_levelTwo(0), time_repairRoutine_levelThree(0) {}

  void print() const {
    std::cout << "HEFT_makespan,deadline_levelOne, deadline_levelTwo,deadline_levelThree,makespan_levelOne,makespan_levelTwo,makespan_levelThree,HEFT_carbon_cost,carbon_cost_levelOne,carbon_cost_levelTwo,carbon_cost_levelThree,time_HEFT,time_deadlineAgnosticMapping_levelOne,time_deadlineAgnosticMapping_levelTwo,time_deadlineAgnosticMapping_levelThree,time_repairRoutine_levelOne,time_repairRoutine_levelTwo,time_repairRoutine_levelThree\n";
    std::cout << HEFT_makespan << "," << deadline_levelOne << "," << deadline_levelTwo << "," << deadline_levelThree << "," << makespan_levelOne << "," << makespan_levelTwo << "," << makespan_levelThree << "," << HEFT_carbon_cost << "," << carbon_cost_levelOne << "," << carbon_cost_levelTwo << "," << carbon_cost_levelThree << "," << time_HEFT << "," << time_deadlineAgnosticMapping_levelOne << "," << time_deadlineAgnosticMapping_levelTwo << "," << time_deadlineAgnosticMapping_levelThree << "," << time_repairRoutine_levelOne << "," << time_repairRoutine_levelTwo << "," << time_repairRoutine_levelThree << std::endl;
  }
};

// ------------------ structs for the model ------------------

struct Edge {
  unsigned int pred;
  unsigned int msg_size;
};

struct Job {
  std::vector<Edge> preds;
  unsigned int id;
};

struct Assignment {
  int processor = -1;
  unsigned int start = 0;
  unsigned int finish = 0;
};

struct Transfer_details {
  unsigned int link_id;
  unsigned int start_time;
  unsigned int end_time;
};

struct Schedule {
  std::vector<Assignment> assign;
  unsigned int makespan = 0;
  unsigned int carbonCost = 0;
  robin_hood::unordered_map<uint64_t, Transfer_details> messages;

  Schedule() = default;
  Schedule(const Schedule&) = default;
  Schedule(Schedule&&) noexcept = default;
  Schedule& operator=(const Schedule&) = default;
  Schedule& operator=(Schedule&&) noexcept = default;

  void clear() noexcept {
    assign.clear();
    makespan = 0;
    carbonCost = 0;
    messages.clear();
  }
};

struct CommInterval {
  unsigned int src_task;
  unsigned int dst_task;

  unsigned int start;
  unsigned int end;
};

struct Communication {
  unsigned int src_task;
  unsigned int dst_task;
  unsigned int src_PE;
  unsigned int dst_PE;
  unsigned int msg_size;
  unsigned int link_id;
  unsigned int finishTime_srcTask;
  unsigned int startTime_of_comm; // stores the result;
  bool is_none = false; // true if src_PE == dst_PE
};

// --------------------------- new data structure for task insertions ---------------------------
struct IntervalSet {
  // Disjoint set of intervals [start, end)
  // key: start, value: end
  // invariant: intervals are disjoint and sorted by start time: [a,b), [c,d) with a < b < c < d
  std::map<unsigned int, unsigned int> intervals;

  inline unsigned int earliest_gap(unsigned int start, unsigned int duration) const {
    if (duration <= 0) return start; // no time needed

    auto it = intervals.upper_bound(start);

    if (it != intervals.begin()) {
      auto prev_it = std::prev(it);
      if (start < prev_it->second) {
        start = prev_it->second; // move start to the end of the previous interval
      }
    }

    while (it != intervals.end() && it->first < start + duration) {
      if (start + duration <= it->first) {
        break; // gap fits
      } 
      if (start < it->second) {
        start = it->second; 
      }
      ++it;
    }
    return start;
  }

  inline void insert_interval(unsigned int start, unsigned int end) {
    if (start >= end) return; // invalid interval

    auto it = intervals.upper_bound(start);

    unsigned int int_start = start, int_end = end;

    // merge previous intervals to save some work later
    if (it != intervals.begin()) {
      auto prev_it = std::prev(it);
      if (prev_it->second >= int_start) {
        int_start = std::min(int_start, prev_it->first);
        int_end = std::max(int_end, prev_it->second);
        it = intervals.erase(prev_it);
      }
    }

    // merge forward touching intervals
    while (it != intervals.end() && it->first <= int_end) {
      int_end = std::max(int_end, it->second);
      it = intervals.erase(it);
    }
    intervals.emplace(int_start, int_end);
  }
};

// ===========================================
// Message ID helper functions
// ===========================================
// Layout: [63-48]=pred ID, [47-32]=task ID, [31-16]=link ID, [15-0]=processor 

inline uint64_t make_message_id(uint16_t pred, uint16_t task, uint16_t link, uint16_t proc) noexcept {
  return  ((uint64_t)pred << 48) |
          ((uint64_t)task << 32) |
          ((uint64_t)link << 16) |
          ((uint64_t)proc); 
}

struct MsgIDFields {
  uint16_t pred;
  uint16_t task;
  uint16_t link;
  uint16_t proc;
};

inline MsgIDFields decode_msg_id(uint64_t msg_id) noexcept {
  MsgIDFields fields;
  fields.pred = (uint16_t)((msg_id >> 48) & 0xFFFF);
  fields.task = (uint16_t)((msg_id >> 32) & 0xFFFF);
  fields.link = (uint16_t)((msg_id >> 16) & 0xFFFF);
  fields.proc = (uint16_t)(msg_id & 0xFFFF);
  return fields;
}

// } // namespace CaWoMap

#include <algorithms/mapper.hpp>
#include <climits>
#include <cassert>
#include <numeric>
#include <chrono>
#include <cmath>
#include <cstdint>

unsigned int LOCAL_SEARCH_MAX_ITERATIONS = 500;

void CaWoMap::prepare_HEFT() {
  running_times.resize(G.getNumNodes());
  for (size_t task = 0; task < G.getNumNodes(); ++task) {
    running_times[task].resize(_config.getNumProcessors());
    for (size_t proc = 0; proc < _config.getNumProcessors(); ++proc) {
      running_times[task][proc] = get_running_time(task, proc);
    }
  }
}

Schedule CaWoMap::HEFT() {
  Schedule& result = HEFT_schedule;
  result.messages.reserve(G.getNumEdges()); // reserve some space for the messages 
  heft_processor_of_task.resize(G.getNumNodes(), UINT_MAX);
  heft_start_and_end_times.resize(G.getNumNodes(), {0,0});
  auto link_id = [this](unsigned int source, unsigned int target) {
    return source + target * _config.getNumProcessors();
  };

  // 1D 
  links.resize((size_t)_config.getNumProcessors() * (size_t)_config.getNumProcessors()); // communication links
  processors.resize((size_t)_config.getNumProcessors()); // processors

  std::vector<unsigned int> arrivals;
  arrivals.reserve(64);
  std::vector<Transfer> transfers;
  transfers.reserve(64);

  unsigned int makespan = 0;

  std::vector<float> upward_rank(G.getNumNodes(), 0.0f);

  std::vector<unsigned int> topological_order; 
  compute_topological_order(topological_order);
  std::reverse(topological_order.begin(), topological_order.end());
  compute_upward_ranks(upward_rank, topological_order);
  std::vector<unsigned int> ranking(G.getNumNodes(), 0); 
  std::iota(ranking.begin(), ranking.end(), 0);
  // sort ranking based on upward rank in descending order
  assert(upward_rank.size() == G.getNumNodes());
  assert(ranking.size() == G.getNumNodes());
  
  // tie-breaking
  std::shuffle(ranking.begin(), ranking.end(), _config.rng); // shuffle 
  std::sort(ranking.begin(), ranking.end(), [this, &upward_rank](unsigned int a, unsigned int b) {
    assert(a < upward_rank.size());
    assert(b < upward_rank.size());
    return upward_rank[a] > upward_rank[b];
  });


  // store PE ready times
  std::vector<unsigned int> PE_ready(_config.getNumProcessors(), 0);

  std::vector<Assignment> assignments(G.getNumNodes());
  result.assign.resize(G.getNumNodes());

  std::vector<Job> jobs(G.getNumNodes());

  for (unsigned int task : ranking) {
    Job& current_job = jobs[task];
    current_job.id = task;
    for (const auto& pred : G.adjList_inNeighbors[task]) {
      Edge pred_edge = {pred.id, pred.weight};
      current_job.preds.push_back(pred_edge);
    }

    unsigned int bestFinish = UINT_MAX;
    unsigned int bestProc = UINT_MAX;
    unsigned int bestStart = UINT_MAX;
    std::vector<Transfer> bestTransfers;

    for (size_t PE = 0; PE < _config.getNumProcessors(); ++PE) {

      arrivals.clear();
      transfers.clear();
      arrivals.reserve(current_job.preds.size());
      transfers.reserve(current_job.preds.size());

      bool feasible = true;

      std::vector<IntervalSet> temp_links(links.size());
      std::vector<bool> touched(links.size(), false); 

      for (const auto& predecessor : current_job.preds) {

        unsigned int pred_id = predecessor.pred;
        unsigned int pred_proc = heft_processor_of_task[pred_id];

        if (pred_proc == UINT_MAX) {
          feasible = false;
          break; // predecessor not scheduled yet
        }
        const unsigned int finishTime_pred = heft_start_and_end_times[pred_id].second;

        
        if (pred_proc == PE) {
          arrivals.push_back(finishTime_pred);
          continue;
        } else {
          const unsigned int link_ID = link_id(pred_proc, PE);
          IntervalSet& link_temp = temp_links[(size_t)link_ID];

          if (!touched[(size_t)link_ID]) {
            if (!links[(size_t)link_ID].intervals.empty()) {
              link_temp.intervals = links[(size_t)link_ID].intervals;
            }
            touched[(size_t)link_ID] = true;
          }

          unsigned int start = finishTime_pred;
          start = link_temp.earliest_gap(start, predecessor.msg_size);
          unsigned int end = start + predecessor.msg_size;

          uint64_t msg_id = make_message_id(
            (uint16_t)pred_id,
            (uint16_t)task,
            (uint16_t)link_ID,
            (uint16_t)PE
          );
          
          arrivals.push_back(end);
          transfers.push_back({link_ID, start, end, msg_id});
          temp_links[(size_t)link_ID].insert_interval(start, end);
        }
      }

      if (!feasible) continue;

      const unsigned int avail = arrivals.empty()
        ? 0
        : *std::max_element(arrivals.begin(), arrivals.end());

      const unsigned int duration_task = running_times[task][PE];
      unsigned int start = processors[(size_t)PE].earliest_gap(avail, duration_task);
      const unsigned int finish = start + duration_task;

      if (finish < bestFinish) {
        bestFinish = finish;
        bestProc = PE;
        bestStart = start;
        bestTransfers = transfers;
      } else if (finish == bestFinish) {
        // coin flip to break ties
        if (flipper.flip()) {
          bestFinish = finish;
          bestProc = PE;
          bestStart = start;
          bestTransfers = transfers;
        }
      }
    }

    if (bestProc == UINT_MAX || bestFinish == UINT_MAX) {
      throw std::runtime_error("No feasible processor found for task " + std::to_string(task) + " in HEFT.");
    }

    assignments[task] = {static_cast<int>(bestProc), bestStart, bestFinish};
    result.assign[task] = {static_cast<int>(bestProc), bestStart, bestFinish};
    heft_processor_of_task[task] = bestProc;
    heft_start_and_end_times[task] = {bestStart, bestFinish};
    PE_ready[bestProc] = bestFinish;
    processors[(size_t)bestProc].insert_interval(bestStart, bestFinish);
    if (bestFinish > makespan) makespan = bestFinish;

    // schedule communications
    for (const auto& transfer : bestTransfers) {
      links[(size_t)transfer.link_id].insert_interval(transfer.start_time, transfer.end_time);
      result.messages[transfer.id] = Transfer_details{transfer.link_id, transfer.start_time, transfer.end_time};
    }
  }  
  
  result.makespan = makespan;
  result.carbonCost = UINT_MAX; // HEFT does not consider carbon cost
  return result;
}

unsigned int CaWoMap::HEFT_compute_carbon_cost_fast() {
  unsigned int total_carbon = 0;

  std::vector<unsigned int> events;
  events.reserve((G.getNumNodes() * 2 + _config.getIntervals().size()));
  for (const auto& point : _config.getIntervals()) {
    events.push_back(point);
  }
  
  // sweep line over every task
  for (const auto& [start, end] : heft_start_and_end_times) {
    events.push_back(start); events.push_back(end);
  }

  // sweep line over every communication
  for (const auto& [msg_id, details] : HEFT_schedule.messages) {
    events.push_back(details.start_time);
    events.push_back(details.end_time);
  }

  std::sort(events.begin(), events.end());
  events.erase(std::unique(events.begin(), events.end()), events.end());
  // store intervals in map
  unsigned int current_interval_id = 0;
  size_t current_interval_iterator = 1;
  unsigned int original_interval_end = _config.getIntervals()[current_interval_iterator];
  std::map<unsigned int, EndpointWithBudget> refined_intervals;
  for (size_t i = 0; i < events.size() - 1; ++i) {
    unsigned int start = events[i];
    unsigned int end = events[i+1];
    if (start >= original_interval_end) {
      current_interval_id++;
      original_interval_end = _config.getIntervals()[++current_interval_iterator];
    }
    refined_intervals[start] = {end, (unsigned int)i, _config.getBudgets()[current_interval_id]};
  }

  // Now we have the refined intervals
  unsigned int bit_vector_size_comp = _config.getNumProcessors();
  std::vector<std::vector<bool>> processor_usage(events.size()-1, std::vector<bool>(bit_vector_size_comp, false));

  unsigned int bit_vector_size_comm = _config.getNumProcessors() * _config.getNumProcessors();
  std::vector<std::vector<bool>> communication_usage(events.size()-1, std::vector<bool>(bit_vector_size_comm, false));

  // mark processor usage
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    unsigned int proc = heft_processor_of_task[task];
    unsigned int start = heft_start_and_end_times[task].first;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      processor_usage[interval_id][proc] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < heft_start_and_end_times[task].second) {
      processor_usage[it->second.interval_id][proc] = true;
      ++it;
    }
  }

  // mark communication usage
  for (const auto& [msg_id, details] : HEFT_schedule.messages) {
    unsigned int link_id = details.link_id;
    unsigned int start = details.start_time;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      communication_usage[interval_id][link_id] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < details.end_time) {
      communication_usage[it->second.interval_id][link_id] = true;
      ++it;
    }
  }

  // now compute the carbon cost per refined interval
  // first we have to assign the link a power value, we have P(P-1) of them but created P^2 links.
  auto power_id = [this](unsigned int link_id) {
    unsigned int src = link_id % _config.getNumProcessors();
    unsigned int tgt = link_id / _config.getNumProcessors();
    if (src < tgt) {
      return src * (_config.getNumProcessors() - 1) + tgt - 1;
    } else {
      return src * (_config.getNumProcessors() - 1) + tgt;
    }
  };

  for (const auto& [start, endpoint] : refined_intervals) {
    unsigned int power = _config.getBasePower();
    for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
      if (processor_usage[endpoint.interval_id][p]) {
        power += _config.getPWork()[p];
      } 
    }

    for (size_t l = 0; l < _config.getNumProcessors() * _config.getNumProcessors(); ++l) {
      if (communication_usage[endpoint.interval_id][l]) {
        unsigned int pid = power_id(l);
        power += _config.getPWorkComm()[pid];
      }
    }

    if (power > endpoint.budget) {
      unsigned int duration = endpoint.interval_end - start;
      total_carbon += (power - endpoint.budget) * duration;
    }
  }

  return total_carbon;
}

unsigned int CaWoMap::final_compute_carbon_cost_fast() {
  unsigned int total_carbon = 0;

  std::vector<unsigned int> events;
  events.reserve((G.getNumNodes() * 2 + _config.getIntervals().size()));
  for (const auto& point : _config.getIntervals()) {
    events.push_back(point);
  }
  
  // sweep line over every task
  for (const auto& [start, end] : final_start_and_end_times) {
    events.push_back(start); events.push_back(end);
  }

  // sweep line over every communication
  for (const auto& [msg_id, details] : final_schedule.messages) {
    events.push_back(details.start_time);
    events.push_back(details.end_time);
  }

  std::sort(events.begin(), events.end());
  events.erase(std::unique(events.begin(), events.end()), events.end());
  // store intervals in map
  unsigned int current_interval_id = 0;
  size_t current_interval_iterator = 1;
  unsigned int original_interval_end = _config.getIntervals()[current_interval_iterator];
  // this works because we do not skip intervals because the interval points are events, too
  std::map<unsigned int, EndpointWithBudget> refined_intervals;
  for (size_t i = 0; i < events.size() - 1; ++i) {
    unsigned int start = events[i];
    unsigned int end = events[i+1];
    if (start >= original_interval_end) {
      current_interval_id++;
      original_interval_end = _config.getIntervals()[++current_interval_iterator];
    }
    refined_intervals[start] = {end, (unsigned int)i, _config.getBudgets()[current_interval_id]};
  }

  // Now we have the refined intervals
  unsigned int bit_vector_size_comp = _config.getNumProcessors();
  std::vector<std::vector<bool>> processor_usage(events.size()-1, std::vector<bool>(bit_vector_size_comp, false));

  unsigned int bit_vector_size_comm = _config.getNumProcessors() * _config.getNumProcessors();
  std::vector<std::vector<bool>> communication_usage(events.size()-1, std::vector<bool>(bit_vector_size_comm, false));

  // mark processor usage
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    unsigned int proc = final_processor_of_task[task];
    unsigned int start = final_start_and_end_times[task].first;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      processor_usage[interval_id][proc] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < final_start_and_end_times[task].second) {
      processor_usage[it->second.interval_id][proc] = true;
      ++it;
    }
  }

  // mark communication usage
  for (const auto& [msg_id, details] : final_schedule.messages) {
    unsigned int link_id = details.link_id;
    unsigned int start = details.start_time;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      communication_usage[interval_id][link_id] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < details.end_time) {
      communication_usage[it->second.interval_id][link_id] = true;
      ++it;
    }
  }

  // now compute the carbon cost per refined interval
  // first we have to assign the link a power value, we have P(P-1) of them but created P^2 links.
  auto power_id = [this](unsigned int link_id) {
    unsigned int src = link_id % _config.getNumProcessors();
    unsigned int tgt = link_id / _config.getNumProcessors();
    if (src < tgt) {
      return src * (_config.getNumProcessors() - 1) + tgt - 1;
    } else {
      return src * (_config.getNumProcessors() - 1) + tgt;
    }
  };

  for (const auto& [start, endpoint] : refined_intervals) {
    unsigned int power = _config.getBasePower();
    for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
      if (processor_usage[endpoint.interval_id][p]) {
        power += _config.getPWork()[p];
      } 
    }

    for (size_t l = 0; l < _config.getNumProcessors() * _config.getNumProcessors(); ++l) {
      if (communication_usage[endpoint.interval_id][l]) {
        unsigned int pid = power_id(l);
        power += _config.getPWorkComm()[pid];
      }
    }

    if (power > endpoint.budget) {
      unsigned int duration = endpoint.interval_end - start;
      total_carbon += (power - endpoint.budget) * duration;
    }
  }

  return total_carbon;
}

std::vector<unsigned long long> CaWoMap::final_carbon_cost_per_interval(std::vector<unsigned long long>* energy_out) {
  return carbon_cost_per_interval(final_start_and_end_times, final_processor_of_task, final_schedule, energy_out);
}

std::vector<unsigned long long> CaWoMap::HEFT_carbon_cost_per_interval(std::vector<unsigned long long>* energy_out) {
  return carbon_cost_per_interval(heft_start_and_end_times, heft_processor_of_task, HEFT_schedule, energy_out);
}

// Same sweep as final_compute_carbon_cost_fast(), but attributes excess energy to the
// original profile interval and accumulates in 64 bit.
std::vector<unsigned long long> CaWoMap::carbon_cost_per_interval(
    const std::vector<std::pair<unsigned int, unsigned int>>& times,
    const std::vector<unsigned int>& procs,
    const Schedule& sched,
    std::vector<unsigned long long>* energy_out) {
  std::vector<unsigned long long> per_interval(_config.getBudgets().size(), 0ULL);
  if (energy_out) energy_out->assign(_config.getBudgets().size(), 0ULL);
  std::vector<unsigned int> original_id_of_refined;

  std::vector<unsigned int> events;
  events.reserve((G.getNumNodes() * 2 + _config.getIntervals().size()));
  for (const auto& point : _config.getIntervals()) {
    events.push_back(point);
  }
  
  // sweep line over every task
  for (const auto& [start, end] : times) {
    events.push_back(start); events.push_back(end);
  }

  // sweep line over every communication
  for (const auto& [msg_id, details] : sched.messages) {
    events.push_back(details.start_time);
    events.push_back(details.end_time);
  }

  std::sort(events.begin(), events.end());
  events.erase(std::unique(events.begin(), events.end()), events.end());
  // store intervals in map
  unsigned int current_interval_id = 0;
  size_t current_interval_iterator = 1;
  unsigned int original_interval_end = _config.getIntervals()[current_interval_iterator];
  // this works because we do not skip intervals because the interval points are events, too
  std::map<unsigned int, EndpointWithBudget> refined_intervals;
  for (size_t i = 0; i < events.size() - 1; ++i) {
    unsigned int start = events[i];
    unsigned int end = events[i+1];
    if (start >= original_interval_end) {
      current_interval_id++;
      original_interval_end = _config.getIntervals()[++current_interval_iterator];
    }
    refined_intervals[start] = {end, (unsigned int)i, _config.getBudgets()[current_interval_id]};
    original_id_of_refined.push_back(current_interval_id);
  }

  // Now we have the refined intervals
  unsigned int bit_vector_size_comp = _config.getNumProcessors();
  std::vector<std::vector<bool>> processor_usage(events.size()-1, std::vector<bool>(bit_vector_size_comp, false));

  unsigned int bit_vector_size_comm = _config.getNumProcessors() * _config.getNumProcessors();
  std::vector<std::vector<bool>> communication_usage(events.size()-1, std::vector<bool>(bit_vector_size_comm, false));

  // mark processor usage
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    unsigned int proc = procs[task];
    unsigned int start = times[task].first;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      processor_usage[interval_id][proc] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < times[task].second) {
      processor_usage[it->second.interval_id][proc] = true;
      ++it;
    }
  }

  // mark communication usage
  for (const auto& [msg_id, details] : sched.messages) {
    unsigned int link_id = details.link_id;
    unsigned int start = details.start_time;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      communication_usage[interval_id][link_id] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < details.end_time) {
      communication_usage[it->second.interval_id][link_id] = true;
      ++it;
    }
  }

  // now compute the carbon cost per refined interval
  // first we have to assign the link a power value, we have P(P-1) of them but created P^2 links.
  auto power_id = [this](unsigned int link_id) {
    unsigned int src = link_id % _config.getNumProcessors();
    unsigned int tgt = link_id / _config.getNumProcessors();
    if (src < tgt) {
      return src * (_config.getNumProcessors() - 1) + tgt - 1;
    } else {
      return src * (_config.getNumProcessors() - 1) + tgt;
    }
  };

  for (const auto& [start, endpoint] : refined_intervals) {
    unsigned int power = _config.getBasePower();
    for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
      if (processor_usage[endpoint.interval_id][p]) {
        power += _config.getPWork()[p];
      } 
    }

    for (size_t l = 0; l < _config.getNumProcessors() * _config.getNumProcessors(); ++l) {
      if (communication_usage[endpoint.interval_id][l]) {
        unsigned int pid = power_id(l);
        power += _config.getPWorkComm()[pid];
      }
    }

    if (energy_out) {
      (*energy_out)[original_id_of_refined[endpoint.interval_id]] +=
          static_cast<unsigned long long>(power) * (endpoint.interval_end - start);
    }
    if (power > endpoint.budget) {
      unsigned long long duration = endpoint.interval_end - start;
      per_interval[original_id_of_refined[endpoint.interval_id]] +=
          static_cast<unsigned long long>(power - endpoint.budget) * duration;
    }
  }

  return per_interval;
}

unsigned int CaWoMap::CWM_compute_carbon_cost_fast() {
  unsigned int total_carbon = 0;

  std::vector<unsigned int> events;
  events.reserve((G.getNumNodes() * 2 + _config.getIntervals().size()));
  for (const auto& point : _config.getIntervals()) {
    events.push_back(point);
  }
  
  // sweep line over every task
  for (const auto& [start, end] : start_and_end_times) {
    events.push_back(start); events.push_back(end);
  }

  // sweep line over every communication
  for (const auto& [msg_id, details] : CWM_schedule.messages) {
    events.push_back(details.start_time);
    events.push_back(details.end_time);
  }

  std::sort(events.begin(), events.end());
  events.erase(std::unique(events.begin(), events.end()), events.end());
  // store intervals in map
  unsigned int current_interval_id = 0;
  size_t current_interval_iterator = 1;
  unsigned int original_interval_end = _config.getIntervals()[current_interval_iterator];
  // this works because we do not skip intervals because the interval points are events, too
  std::map<unsigned int, EndpointWithBudget> refined_intervals;
  for (size_t i = 0; i < events.size() - 1; ++i) {
    unsigned int start = events[i];
    unsigned int end = events[i+1];
    if (start >= original_interval_end) {
      current_interval_id++;
      original_interval_end = _config.getIntervals()[++current_interval_iterator];
    }
    refined_intervals[start] = {end, (unsigned int)i, _config.getBudgets()[current_interval_id]};
  }

  // Now we have the refined intervals
  unsigned int bit_vector_size_comp = _config.getNumProcessors();
  std::vector<std::vector<bool>> processor_usage(events.size()-1, std::vector<bool>(bit_vector_size_comp, false));

  unsigned int bit_vector_size_comm = _config.getNumProcessors() * _config.getNumProcessors();
  std::vector<std::vector<bool>> communication_usage(events.size()-1, std::vector<bool>(bit_vector_size_comm, false));

  // mark processor usage
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    unsigned int proc = processor_of_task[task];
    unsigned int start = start_and_end_times[task].first;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      processor_usage[interval_id][proc] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < start_and_end_times[task].second) {
      processor_usage[it->second.interval_id][proc] = true;
      ++it;
    }
  }

  // mark communication usage
  for (const auto& [msg_id, details] : CWM_schedule.messages) {
    unsigned int link_id = details.link_id;
    unsigned int start = details.start_time;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      communication_usage[interval_id][link_id] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < details.end_time) {
      communication_usage[it->second.interval_id][link_id] = true;
      ++it;
    }
  }

  // now compute the carbon cost per refined interval
  // first we have to assign the link a power value, we have P(P-1) of them but created P^2 links.
  auto power_id = [this](unsigned int link_id) {
    unsigned int src = link_id % _config.getNumProcessors();
    unsigned int tgt = link_id / _config.getNumProcessors();
    if (src < tgt) {
      return src * (_config.getNumProcessors() - 1) + tgt - 1;
    } else {
      return src * (_config.getNumProcessors() - 1) + tgt;
    }
  };

  for (const auto& [start, endpoint] : refined_intervals) {
    unsigned int power = _config.getBasePower();
    for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
      if (processor_usage[endpoint.interval_id][p]) {
        power += _config.getPWork()[p];
      } 
    }

    for (size_t l = 0; l < _config.getNumProcessors() * _config.getNumProcessors(); ++l) {
      if (communication_usage[endpoint.interval_id][l]) {
        unsigned int pid = power_id(l);
        power += _config.getPWorkComm()[pid];
      }
    }

    if (power > endpoint.budget) {
      unsigned int duration = endpoint.interval_end - start;
      total_carbon += (power - endpoint.budget) * duration;
    }
  }

  return total_carbon;
}

Schedule CaWoMap::CaWoMap_Init(const std::string& variant) {
  double THRESHOLD = 0.6;
  double offset = 1.0;
  if (_config.getClusterVariant() == "small") {
    offset = 0.2;
  } else {
    offset = 0.4;
  }
  prepare_processor_subsets(offset);
  Schedule& result = CWM_schedule;
  result.messages.reserve(G.getNumEdges()); // reserve some space for the messages
  processor_of_task.resize(G.getNumNodes(), UINT_MAX);
  start_and_end_times.resize(G.getNumNodes(), {0,0});

  // 1D 
  CWM_links.resize((size_t)_config.getNumProcessors() * (size_t)_config.getNumProcessors()); // communication links
  CWM_processors.resize((size_t)_config.getNumProcessors()); // processors

  std::vector<unsigned int> arrivals;
  arrivals.reserve(64);
  std::vector<Transfer> transfers;
  transfers.reserve(64);

  unsigned int& makespan = result.makespan;
  makespan = 0;

  std::vector<float> upward_rank(G.getNumNodes(), 0.0f);

  
  std::vector<unsigned int> topological_order; 
  compute_topological_order(topological_order);
  std::reverse(topological_order.begin(), topological_order.end());
  compute_upward_ranks(upward_rank, topological_order);
  std::vector<unsigned int> ranking(G.getNumNodes(), 0); 
  std::iota(ranking.begin(), ranking.end(), 0);
  // sort ranking based on upward rank in descending order
  assert(upward_rank.size() == G.getNumNodes());
  assert(ranking.size() == G.getNumNodes());
  // tie-breaking
  std::shuffle(ranking.begin(), ranking.end(), _config.rng); // shuffle 
  std::sort(ranking.begin(), ranking.end(), [this, &upward_rank](unsigned int a, unsigned int b) {
    assert(a < upward_rank.size());
    assert(b < upward_rank.size());
    return upward_rank[a] > upward_rank[b];
  });

  std::vector<Assignment> assignments(G.getNumNodes());
  result.assign.resize(G.getNumNodes());
  result.makespan = 0;

  std::vector<Job> jobs(G.getNumNodes());
  for (unsigned int task : ranking) {
    Job& current_job = jobs[task];
    current_job.id = task;
    for (const auto& pred : G.adjList_inNeighbors[task]) {
      Edge pred_edge = {pred.id, pred.weight};
      current_job.preds.push_back(pred_edge); 
    }

    auto is_in_same_interval = [this](unsigned int id, unsigned int time) {
      return (_config.getIntervals()[id] <= time && time < _config.getIntervals()[id+1]);
    };

    unsigned int EST = compute_EST_without_communications(task);
    unsigned int interval_id = getIntervalId(EST);
    std::vector<PE>& current_PE_subset = all_processor_subsets[interval_id];
    choice bestChoice{};
    find_choice(
      task,
      bestChoice,
      current_job,
      arrivals,
      transfers,
      current_PE_subset,
      0
    );      

    if (variant == "strong" || variant == "local-search") {
      unsigned int counter = 0;
      unsigned int realStartTime = bestChoice.bestStart;
      while(!is_in_same_interval(interval_id, realStartTime) && counter < 3 && interval_id + 1 < all_processor_subsets.size()) {
        ++interval_id;
        assert(interval_id >= 0 && interval_id < _config.getIntervals().size() && interval_id < all_processor_subsets.size());
        current_PE_subset = all_processor_subsets[interval_id]; 
        unsigned int not_earlier_than = _config.getIntervals()[interval_id]; // this is the interval start
        find_choice(
          task, 
          bestChoice, 
          current_job, 
          arrivals,
          transfers, 
          current_PE_subset,
          not_earlier_than
        );
        realStartTime = bestChoice.bestStart;
        counter++;
      }
      counter = 0;
    } else if (variant == "super-strong") {
      unsigned int realStartTime = bestChoice.bestStart;
      unsigned int reject_counter = 0;
      bool reject = false;
      while(!is_in_same_interval(interval_id, realStartTime) || reject) {
        reject = false;
        ++interval_id;
        assert(interval_id >= 0 && interval_id < _config.getIntervals().size() && interval_id < all_processor_subsets.size());
        current_PE_subset = all_processor_subsets[interval_id]; 
        unsigned int not_earlier_than = _config.getIntervals()[interval_id]; // this is the interval start
        find_choice(
          task, 
          bestChoice, 
          current_job, 
          arrivals,
          transfers, 
          current_PE_subset,
          not_earlier_than
        );
        realStartTime = bestChoice.bestStart;
        // if more than THRESHOLD of the tasks running time is outside the interval, reject this choice
        if (is_in_same_interval(interval_id, realStartTime) && reject_counter < 3) {
          unsigned int time_inside = _config.getIntervals()[interval_id+1] - bestChoice.bestStart;
          double perc_inside = static_cast<double>(time_inside) / static_cast<double>(bestChoice.bestFinish - bestChoice.bestStart);
          if (perc_inside >= THRESHOLD) {
            reject = false;
          } else {
            reject = true;
            reject_counter++;
          }
        }
      }
    } 

    // schedule the decision
    if (bestChoice.bestProc == UINT_MAX || bestChoice.bestFinish == UINT_MAX) {
      throw std::runtime_error("No feasible processor found for task " + std::to_string(task) + " in CaWoMap_Init.");
    }

    assignments[task] = {static_cast<int>(bestChoice.bestProc), bestChoice.bestStart, bestChoice.bestFinish};
    result.assign[task] = {static_cast<int>(bestChoice.bestProc), bestChoice.bestStart, bestChoice.bestFinish};
    processor_of_task[task] = bestChoice.bestProc;
    start_and_end_times[task] = {bestChoice.bestStart, bestChoice.bestFinish};
    CWM_processors[(size_t)bestChoice.bestProc].insert_interval(bestChoice.bestStart, bestChoice.bestFinish);
    if (bestChoice.bestFinish > makespan) makespan = bestChoice.bestFinish;

    // schedule communications
    for (const auto& transfer : bestChoice.bestTransfers) {
      CWM_links[(size_t)transfer.link_id].insert_interval(transfer.start_time, transfer.end_time);
      result.messages[transfer.id] = Transfer_details{transfer.link_id, transfer.start_time, transfer.end_time};
    }
  }

  result.makespan = makespan;
  result.carbonCost = UINT_MAX; // to be computed later

  if (variant == "local-search") {
    local_search_routine(result.makespan);
  }

  return result;
}

void CaWoMap::local_search_routine_final(unsigned int& makespan, unsigned int deadline) {
  unsigned int iteration = 0;
  bool found_task = true;
  while (iteration < LOCAL_SEARCH_MAX_ITERATIONS && makespan <= deadline) {
    found_task = local_search_final(deadline);
    if (!found_task) {
      break;
    }
    // update makespan
    for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
      if (final_start_and_end_times[task].second > makespan) {
        makespan = final_start_and_end_times[task].second;
      }
    }
    iteration++;
  }
}

bool CaWoMap::local_search_final(unsigned int deadline) {
  // First, compute the refined intervals and the budget per refined interval as in the carbon cost computation

  std::vector<interval_with_budget_and_id> refined_intervals_vector;
  std::vector<unsigned int> events;
  events.reserve((G.getNumNodes() * 2 + _config.getIntervals().size()));
  for (const auto& point : _config.getIntervals()) {
    events.push_back(point);
  }
  
  // sweep line over every task
  for (const auto& [start, end] : final_start_and_end_times) {
    events.push_back(start); events.push_back(end);
  }

  // sweep line over every communication
  for (const auto& [msg_id, details] : final_schedule.messages) {
    events.push_back(details.start_time);
    events.push_back(details.end_time);
  }

  std::sort(events.begin(), events.end());
  events.erase(std::unique(events.begin(), events.end()), events.end());
  // store intervals in map
  unsigned int current_interval_id = 0;
  size_t current_interval_iterator = 1;
  unsigned int original_interval_end = _config.getIntervals()[current_interval_iterator];
  // this works because we do not skip intervals because the interval points are events, too
  std::map<unsigned int, EndpointWithBudget> refined_intervals;
  for (size_t i = 0; i < events.size() - 1; ++i) {
    unsigned int start = events[i];
    unsigned int end = events[i+1];
    if (start >= original_interval_end) {
      current_interval_id++;
      original_interval_end = _config.getIntervals()[++current_interval_iterator];
    }
    refined_intervals[start] = {end, (unsigned int)i, _config.getBudgets()[current_interval_id]};
  }

  // Now we have the refined intervals
  unsigned int bit_vector_size_comp = _config.getNumProcessors();
  std::vector<std::vector<bool>> processor_usage(events.size()-1, std::vector<bool>(bit_vector_size_comp, false));

  unsigned int bit_vector_size_comm = _config.getNumProcessors() * _config.getNumProcessors();
  std::vector<std::vector<bool>> communication_usage(events.size()-1, std::vector<bool>(bit_vector_size_comm, false));

  // mark processor usage
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    unsigned int proc = final_processor_of_task[task];
    unsigned int start = final_start_and_end_times[task].first;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      processor_usage[interval_id][proc] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < final_start_and_end_times[task].second) {
      processor_usage[it->second.interval_id][proc] = true;
      ++it;
    }
  }

  // mark communication usage
  for (const auto& [msg_id, details] : final_schedule.messages) {
    unsigned int link_id = details.link_id;
    unsigned int start = details.start_time;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      communication_usage[interval_id][link_id] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < details.end_time) {
      communication_usage[it->second.interval_id][link_id] = true;
      ++it;
    }
  }

  // now compute the carbon cost per refined interval
  // first we have to assign the link a power value, we have P(P-1) of them but created P^2 links.
  refined_intervals_vector.resize(refined_intervals.size());
  auto power_id = [this](unsigned int link_id) {
    unsigned int src = link_id % _config.getNumProcessors();
    unsigned int tgt = link_id / _config.getNumProcessors();
    if (src < tgt) {
      return src * (_config.getNumProcessors() - 1) + tgt - 1;
    } else {
      return src * (_config.getNumProcessors() - 1) + tgt;
    }
  };

  unsigned int idx = 0;
  for (const auto& [start, endpoint] : refined_intervals) {
    interval_with_budget_and_id interval_entry;
    interval_entry.start = start;
    interval_entry.end = endpoint.interval_end;
    interval_entry.id = idx;
    interval_entry.budget = endpoint.budget;
    unsigned int power = _config.getBasePower();
    for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
      if (processor_usage[endpoint.interval_id][p]) {
        power += _config.getPWork()[p];
      } 
    }

    for (size_t l = 0; l < _config.getNumProcessors() * _config.getNumProcessors(); ++l) {
      if (communication_usage[endpoint.interval_id][l]) {
        unsigned int pid = power_id(l);
        power += _config.getPWorkComm()[pid];
      }
    }
    interval_entry.power = power;
    refined_intervals_vector[idx] = interval_entry;
    idx++;
  }

 

  unsigned int iteration = 0;
  while (iteration < 1) {
    /*
    * pick one interval of which the power exceeds the budget
    */
    interval_with_budget_and_id picked_interval;
    bool found = false;
    for (const auto& interval : refined_intervals_vector) {
      if (interval.power > interval.budget) {
        picked_interval = interval;
        found = true;
        break;
      }
    }
    if (!found) return false;

    // look at all tasks that run before this interval.
    std::vector<unsigned int> previous_tasks;
    std::vector<unsigned int> candidate_tasks;
    previous_tasks.reserve(G.getNumNodes());
    std::vector<std::pair<uint64_t, Transfer_details>> affected_messages;
    affected_messages.reserve(G.getNumEdges()/2);
    for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
      if (final_start_and_end_times[task].second <= picked_interval.start) {
        previous_tasks.push_back(task);
      }
      if (
        final_start_and_end_times[task].first < picked_interval.end &&
        final_start_and_end_times[task].second > picked_interval.start
      ) {
        candidate_tasks.push_back(task);
       
      }
    }
    if (candidate_tasks.size() == 0) return false;
    std::shuffle(candidate_tasks.begin(), candidate_tasks.end(), _config.rng);
    unsigned int task_to_reschedule = candidate_tasks[0];
    
    std::vector<unsigned int> later_tasks;
    later_tasks.reserve(G.getNumNodes());
    for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
      if (final_start_and_end_times[task].first >= picked_interval.end) {
        later_tasks.push_back(task);
      }
    }

    include_later_tasks_in_interval_final(task_to_reschedule, picked_interval.end, later_tasks);

    prevent_overlaps_in_later_tasks_final(task_to_reschedule, later_tasks);

   
    unsigned int move = picked_interval.end - final_start_and_end_times[task_to_reschedule].first;
    // all later tasks get shifted by move as well
    // Hence, if we have a deadline, we decrease the move if needed
    unsigned int latest_ending = start_and_end_times[task_to_reschedule].second;
    for (const auto& task: later_tasks) {
      if (final_start_and_end_times[task].second > latest_ending) {
        latest_ending = final_start_and_end_times[task].second;
      }
    }
    if (deadline > 0) {
      if (latest_ending >= deadline) {
        return false;
      } else {
        move = std::min(move, deadline - latest_ending); 
      }
    }
  
    final_start_and_end_times[task_to_reschedule].first += move;
    final_start_and_end_times[task_to_reschedule].second += move;
    for (const auto& succ : G.adjList_outNeighbors[task_to_reschedule]) {
      if (final_processor_of_task[task_to_reschedule] == final_processor_of_task[succ.id]) continue; // no message if on same processor
      uint64_t msg_id = make_message_id(
        (uint16_t)task_to_reschedule,
        (uint16_t)succ.id,
        (uint16_t)(final_processor_of_task[task_to_reschedule] + final_processor_of_task[succ.id] * _config.getNumProcessors()),
        (uint16_t)final_processor_of_task[succ.id]
      );
      affected_messages.push_back({msg_id, final_schedule.messages.at(msg_id)});
    }

    for (const auto& task : later_tasks) {
      for (const auto& succ : G.adjList_outNeighbors[task]) {
        if (final_processor_of_task[task] == final_processor_of_task[succ.id]) continue; // no message if on same processor
        uint64_t msg_id = make_message_id(
          (uint16_t)task,
          (uint16_t)succ.id,
          (uint16_t)(final_processor_of_task[task] + final_processor_of_task[succ.id] * _config.getNumProcessors()),
          (uint16_t)final_processor_of_task[succ.id]
        );
        affected_messages.push_back({msg_id, final_schedule.messages.at(msg_id)});
      }
    }

    prevent_overlaps_in_channels_final(affected_messages);

    // Now move every task in later_tasks by
    for (const auto& task : later_tasks) {
      final_start_and_end_times[task].first += move;
      final_start_and_end_times[task].second += move;
    }

    // now we also have to shift all outgoing messages of the rescheduled tasks.
    for (const auto& [msg_id, details] : affected_messages) {
      final_schedule.messages[msg_id] = Transfer_details{
        details.link_id,
        details.start_time + move,
        details.end_time + move
      };
    }
    iteration++;
  }
  return true;
}

void CaWoMap::local_search_routine(unsigned int& makespan, unsigned int deadline) {
  unsigned int iteration = 0;
  bool found_task = true;
  while (iteration < LOCAL_SEARCH_MAX_ITERATIONS) {
    found_task = local_search(deadline);
    if (!found_task) break;
    // update makespan
    for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
      if (start_and_end_times[task].second > makespan) {
        makespan = start_and_end_times[task].second;
      }
    }
    iteration++;
  }
}

bool CaWoMap::local_search(unsigned int deadline) {
  // First, compute the refined intervals and the budget per refined interval as in the carbon cost computation

  std::vector<interval_with_budget_and_id> refined_intervals_vector;
  std::vector<unsigned int> events;
  events.reserve((G.getNumNodes() * 2 + _config.getIntervals().size()));
  for (const auto& point : _config.getIntervals()) {
    events.push_back(point);
  }
  
  // sweep line over every task
  for (const auto& [start, end] : start_and_end_times) {
    events.push_back(start); events.push_back(end);
  }

  // sweep line over every communication
  for (const auto& [msg_id, details] : CWM_schedule.messages) {
    events.push_back(details.start_time);
    events.push_back(details.end_time);
  }

  std::sort(events.begin(), events.end());
  events.erase(std::unique(events.begin(), events.end()), events.end());
  // store intervals in map
  unsigned int current_interval_id = 0;
  size_t current_interval_iterator = 1;
  unsigned int original_interval_end = _config.getIntervals()[current_interval_iterator];
  // this works because we do not skip intervals because the interval points are events, too
  std::map<unsigned int, EndpointWithBudget> refined_intervals;
  for (size_t i = 0; i < events.size() - 1; ++i) {
    unsigned int start = events[i];
    unsigned int end = events[i+1];
    if (start >= original_interval_end) {
      current_interval_id++;
      original_interval_end = _config.getIntervals()[++current_interval_iterator];
    }
    refined_intervals[start] = {end, (unsigned int)i, _config.getBudgets()[current_interval_id]};
  }

  // Now we have the refined intervals
  unsigned int bit_vector_size_comp = _config.getNumProcessors();
  std::vector<std::vector<bool>> processor_usage(events.size()-1, std::vector<bool>(bit_vector_size_comp, false));

  unsigned int bit_vector_size_comm = _config.getNumProcessors() * _config.getNumProcessors();
  std::vector<std::vector<bool>> communication_usage(events.size()-1, std::vector<bool>(bit_vector_size_comm, false));

  // mark processor usage
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    unsigned int proc = processor_of_task[task];
    unsigned int start = start_and_end_times[task].first;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      processor_usage[interval_id][proc] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < start_and_end_times[task].second) {
      processor_usage[it->second.interval_id][proc] = true;
      ++it;
    }
  }

  // mark communication usage
  for (const auto& [msg_id, details] : CWM_schedule.messages) {
    unsigned int link_id = details.link_id;
    unsigned int start = details.start_time;
    auto it = refined_intervals.upper_bound(start);
    unsigned int interval_id = 0;
    if (it != refined_intervals.begin()) {
      --it;
      interval_id = it->second.interval_id;
      communication_usage[interval_id][link_id] = true;
    }
    ++it; 
    while (it != refined_intervals.end() && it->first < details.end_time) {
      communication_usage[it->second.interval_id][link_id] = true;
      ++it;
    }
  }

  // now compute the carbon cost per refined interval
  // first we have to assign the link a power value, we have P(P-1) of them but created P^2 links.
  refined_intervals_vector.resize(refined_intervals.size());
  auto power_id = [this](unsigned int link_id) {
    unsigned int src = link_id % _config.getNumProcessors();
    unsigned int tgt = link_id / _config.getNumProcessors();
    if (src < tgt) {
      return src * (_config.getNumProcessors() - 1) + tgt - 1;
    } else {
      return src * (_config.getNumProcessors() - 1) + tgt;
    }
  };

  unsigned int idx = 0;
  for (const auto& [start, endpoint] : refined_intervals) {
    interval_with_budget_and_id interval_entry;
    interval_entry.start = start;
    interval_entry.end = endpoint.interval_end;
    interval_entry.id = idx;
    interval_entry.budget = endpoint.budget;
    unsigned int power = _config.getBasePower();
    for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
      if (processor_usage[endpoint.interval_id][p]) {
        power += _config.getPWork()[p];
      } 
    }

    for (size_t l = 0; l < _config.getNumProcessors() * _config.getNumProcessors(); ++l) {
      if (communication_usage[endpoint.interval_id][l]) {
        unsigned int pid = power_id(l);
        power += _config.getPWorkComm()[pid];
      }
    }
    interval_entry.power = power;
    refined_intervals_vector[idx] = interval_entry;
    idx++;
  }

  unsigned int iteration = 0;
  while (iteration < 1) {
    /*
    * pick one interval of which the power exceeds the budget
    */
    interval_with_budget_and_id picked_interval;
    bool found = false;
    for (const auto& interval : refined_intervals_vector) {
      if (interval.power > interval.budget) {
        picked_interval = interval;
        found = true;
        break;
      }
    }
    if (!found) return false; 

    // look at all tasks that run before this interval.
    std::vector<unsigned int> previous_tasks;
    std::vector<unsigned int> candidate_tasks;
    previous_tasks.reserve(G.getNumNodes());
    std::vector<std::pair<uint64_t, Transfer_details>> affected_messages;
    affected_messages.reserve(G.getNumEdges()/2);
    for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
      if (start_and_end_times[task].second <= picked_interval.start) {
        previous_tasks.push_back(task);
      }
      if (
        start_and_end_times[task].first < picked_interval.end &&
        start_and_end_times[task].second > picked_interval.start
      ) {
        candidate_tasks.push_back(task);
      }
    }
    // Now pick a random candidate task
    if (candidate_tasks.size() == 0) {
      return false;
    }

    std::shuffle(candidate_tasks.begin(), candidate_tasks.end(), _config.rng);
    unsigned int task_to_reschedule = candidate_tasks[0];

    std::vector<unsigned int> later_tasks;
    later_tasks.reserve(G.getNumNodes());
  
    for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
      if (start_and_end_times[task].first >= picked_interval.end) {
        later_tasks.push_back(task);
      }
    }

    include_later_tasks_in_interval(task_to_reschedule, picked_interval.end, later_tasks);

    prevent_overlaps_in_later_tasks(task_to_reschedule, later_tasks);

    
    unsigned int move = picked_interval.end - start_and_end_times[task_to_reschedule].first;
    // all later tasks get shifted by move as well
    // Hence, if we have a deadline, we decrease the move if needed
    unsigned int latest_ending = 0;
    for (const auto& task: later_tasks) {
      if (start_and_end_times[task].second > latest_ending) {
        latest_ending = start_and_end_times[task].second;
      }
    }
    if (deadline > 0) {
      if (latest_ending >= deadline) {
        return false;
      } else {
        move = std::min(move, deadline - latest_ending);
      }
    }
    start_and_end_times[task_to_reschedule].first += move;
    start_and_end_times[task_to_reschedule].second += move;
    for (const auto& succ : G.adjList_outNeighbors[task_to_reschedule]) {
      if (processor_of_task[task_to_reschedule] == processor_of_task[succ.id]) continue; // no message if on same processor
      uint64_t msg_id = make_message_id(
        (uint16_t)task_to_reschedule,
        (uint16_t)succ.id,
        (uint16_t)(processor_of_task[task_to_reschedule] + processor_of_task[succ.id] * _config.getNumProcessors()),
        (uint16_t)processor_of_task[succ.id]
      );
      affected_messages.push_back({msg_id, CWM_schedule.messages.at(msg_id)});
    }
  

    for (const auto& task : later_tasks) {
      for (const auto& succ : G.adjList_outNeighbors[task]) {
        if (processor_of_task[task] == processor_of_task[succ.id]) continue; // no message if on same processor
        uint64_t msg_id = make_message_id(
          (uint16_t)task,
          (uint16_t)succ.id,
          (uint16_t)(processor_of_task[task] + processor_of_task[succ.id] * _config.getNumProcessors()),
          (uint16_t)processor_of_task[succ.id]
        );
        affected_messages.push_back({msg_id, CWM_schedule.messages.at(msg_id)});
      }
    }

    prevent_overlaps_in_channels(affected_messages);
    // Now move every task in later_tasks by
    for (const auto& task : later_tasks) {
      start_and_end_times[task].first += move;
      start_and_end_times[task].second += move;
    }

    // now we also have to shift all outgoing messages of the rescheduled tasks.
    for (const auto& [msg_id, details] : affected_messages) {
      CWM_schedule.messages[msg_id] = Transfer_details{
        details.link_id,
        details.start_time + move,
        details.end_time + move
      };
    }
    iteration++;
  }
  return true;
}

void CaWoMap::guarantee_deadline_routine(Schedule& S, const unsigned int deadline) {
  // first, compute current makespan
  unsigned int current_makespan = 0;
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    if (start_and_end_times[task].second > current_makespan) {
      current_makespan = start_and_end_times[task].second;
    }
  }

  if (current_makespan <= deadline) {
    final_schedule = CWM_schedule;
    final_start_and_end_times = start_and_end_times;
    final_processor_of_task = processor_of_task;
    return;
  }

  final_schedule = S;
  unsigned int threshold = deadline;
  unsigned int threshold_guarantee = 0;

  // try basic
  guarantee_deadline(deadline);
  // update current makespan
  current_makespan = 0;
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    if (final_start_and_end_times[task].second > current_makespan) {
      current_makespan = final_start_and_end_times[task].second;
    }
  }
  if (current_makespan <= deadline) {} else {
    unsigned int total_makespan = 0;
    while (threshold_guarantee + 1 < threshold) {
      // Invariant: threshold_guarantee always meets the deadline.
      unsigned int mid = threshold_guarantee + (threshold - threshold_guarantee) / 2;
      guarantee_deadline(mid);
      // update current makespan
      current_makespan = 0;
      for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
        if (final_start_and_end_times[task].second > current_makespan) {
          current_makespan = final_start_and_end_times[task].second;
        }
      }
      if (current_makespan <= deadline) {
        threshold_guarantee = mid;
      } else {
        threshold = mid;
      }
    }
    for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
      if (final_start_and_end_times[task].second > total_makespan) {
        total_makespan = final_start_and_end_times[task].second;
      }
    } 
    guarantee_deadline(threshold_guarantee); // the invariant guarantees that this works
  }
  // Now optimize the final schedule if we exaggerated the deadline repair
  unsigned int total_final_makespan = 0;
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    if (final_start_and_end_times[task].second > total_final_makespan) {
      total_final_makespan = final_start_and_end_times[task].second;
    }
  }
  local_search_routine_final(total_final_makespan, deadline);
  total_final_makespan = 0;
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    if (final_start_and_end_times[task].second > total_final_makespan) {
      total_final_makespan = final_start_and_end_times[task].second;
    }
  }
}

unsigned int CaWoMap::compute_final_makespan() {
  unsigned int final_makespan = 0;
  for (size_t task = 0; task < G.getNumNodes(); ++task) {
    if (final_start_and_end_times[task].second > final_makespan) {
      final_makespan = final_start_and_end_times[task].second;
    }
  }
  return final_makespan;
}

void CaWoMap::include_successors_DFS(unsigned int task, std::vector<bool>& is_included) {
  for (const auto& succ : G.adjList_outNeighbors[task]) {
    if (!is_included[succ.id]) {
      is_included[succ.id] = true;
      include_successors_DFS(succ.id, is_included);
    }
  }
}

void CaWoMap::guarantee_deadline(const unsigned int threshold) {
  std::mt19937 local_rng(_config.getRandomSeed() + 1);
  std::bernoulli_distribution coin(0.5);
  final_schedule.clear();
  std::vector<unsigned int> topological_order; 
  std::vector<float> upward_rank(G.getNumNodes(), 0.0f);
  topological_order.reserve(G.getNumNodes());
  compute_topological_order(topological_order);
  std::reverse(topological_order.begin(), topological_order.end());
  compute_upward_ranks(upward_rank, topological_order);
  std::vector<unsigned int> ranking(G.getNumNodes(), 0); 
  std::iota(ranking.begin(), ranking.end(), 0);
  // sort ranking based on upward rank in descending order
  assert(upward_rank.size() == G.getNumNodes());
  assert(ranking.size() == G.getNumNodes());
  // tie-breaking
  std::shuffle(ranking.begin(), ranking.end(), local_rng); // shuffle 
  std::sort(ranking.begin(), ranking.end(), [this, &upward_rank](unsigned int a, unsigned int b) {
    assert(a < upward_rank.size());
    assert(b < upward_rank.size());
    return upward_rank[a] > upward_rank[b];
  });

  std::vector<bool> is_included(G.getNumNodes(), false);


  for (const auto& task : ranking) {
    if (start_and_end_times[task].second > threshold) {
      is_included[task] = true;
    }
  }

  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    if (is_included[task]) {
      include_successors_DFS(task, is_included);
    }
  }
  
  std::vector<unsigned int> tasks_to_consider;
  tasks_to_consider.reserve(G.getNumNodes());

  for (const auto& task : ranking) {
    if (is_included[task]) {
      tasks_to_consider.push_back(task);
    }
  }



  // Now we have a ranking of the tasks that we want to reschedule using HEFT.
  final_schedule.messages.reserve(G.getNumEdges());
  unsigned int& final_makespan = final_schedule.makespan;

  final_links.clear();
  final_processors.clear();
  final_start_and_end_times.clear();
  final_processor_of_task.clear();
  final_links.resize((size_t)_config.getNumProcessors() * (size_t)_config.getNumProcessors()); // communication links
  final_processors.resize((size_t)_config.getNumProcessors()); // processors
  final_start_and_end_times.resize(G.getNumNodes(), {0,0});
  final_processor_of_task.resize(G.getNumNodes(), UINT_MAX);
  final_schedule.assign.resize(G.getNumNodes());
  // For all not included tasks, we keep their previous assignment
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    if (!is_included[task]) {
      final_start_and_end_times[task] = start_and_end_times[task];
      final_processor_of_task[task] = processor_of_task[task];
      final_processors[(size_t)processor_of_task[task]].insert_interval(
        start_and_end_times[task].first,
        start_and_end_times[task].second
      );
      // Now all the messages. But only those they get from incoming tasks.
      // by design they are all not included. 
      // Conceptually we are cutting the graph into two parts where edges 
      // only run from one part to the other.
      for (const auto& pred : G.adjList_inNeighbors[task]) {
        if (is_included[pred.id]) std::cout << "Error: predecessor " << pred.id << " of non-included task " << task << " is included!" << std::endl;
        if (processor_of_task[pred.id] == processor_of_task[task]) continue;
        uint64_t msg_id = make_message_id(
          (uint16_t)pred.id,
          (uint16_t)task,
          (uint16_t)(processor_of_task[pred.id] + processor_of_task[task] * _config.getNumProcessors()),
          (uint16_t)processor_of_task[task]
        );
        final_schedule.messages[msg_id] = CWM_schedule.messages.at(msg_id);
        final_links[(size_t)(processor_of_task[pred.id] + processor_of_task[task] * _config.getNumProcessors())].insert_interval(
          CWM_schedule.messages.at(msg_id).start_time,
          CWM_schedule.messages.at(msg_id).end_time
        );
      }
    }
  }
  auto link_id = [this](unsigned int source, unsigned int target) {
    return source + target * _config.getNumProcessors();
  };
  // Now we can find new assignments for the tasks to consider using the HEFT-SL approach
  std::vector<Job> jobs(G.getNumNodes());
  std::vector<unsigned int> arrivals;
  std::vector<Transfer> transfers;
  for (unsigned int task : tasks_to_consider) {
    Job& current_job = jobs[task];
    current_job.id = task;
    for (const auto& pred : G.adjList_inNeighbors[task]) {
      // these are all communications that have to be scheduled
      Edge pred_edge = {pred.id, pred.weight};
      current_job.preds.push_back(pred_edge);
    }

    unsigned int bestFinish = UINT_MAX;
    unsigned int bestProc = UINT_MAX;
    unsigned int bestStart = UINT_MAX;
    std::vector<Transfer> bestTransfers;

    for (size_t PE = 0; PE < _config.getNumProcessors(); ++PE) {

      arrivals.clear();
      transfers.clear();
      arrivals.reserve(current_job.preds.size());
      transfers.reserve(current_job.preds.size());

      bool feasible = true;

      std::vector<IntervalSet> temp_links(final_links.size());
      std::vector<bool> touched(final_links.size(), false);

      for (const auto& predecessor : current_job.preds) {
        unsigned int pred_id = predecessor.pred;
        unsigned int pred_proc = final_processor_of_task[pred_id];

        if (pred_proc == UINT_MAX) {
          feasible = false;
          break; // predecessor not scheduled yet
        }
        const unsigned int finishTime_pred = final_start_and_end_times[pred_id].second;

        if (pred_proc == PE) {
          arrivals.push_back(finishTime_pred);
          continue;
        } else {
          const unsigned int link_ID = link_id(pred_proc, PE);
          IntervalSet& link_temp = temp_links[(size_t)link_ID];

          if (!touched[(size_t)link_ID]) {
            if (!final_links[(size_t)link_ID].intervals.empty()) {
              link_temp.intervals = final_links[(size_t)link_ID].intervals;
            }
            touched[(size_t)link_ID] = true;
          }

          unsigned int start = finishTime_pred;
          start = link_temp.earliest_gap(start, predecessor.msg_size);
          unsigned int end = start + predecessor.msg_size;

          uint64_t msg_id = make_message_id(
            (uint16_t)pred_id,
            (uint16_t)task,
            (uint16_t)link_ID,
            (uint16_t)PE
          );

          arrivals.push_back(end);
          transfers.push_back({link_ID, start, end, msg_id});
          temp_links[(size_t)link_ID].insert_interval(start, end);
        }
      }

      if (!feasible) continue;

      const unsigned int avail = arrivals.empty()
        ? 0
        : *std::max_element(arrivals.begin(), arrivals.end());

      const unsigned int duration_task = running_times[task][PE];
      const unsigned int start = final_processors[(size_t)PE].earliest_gap(avail, duration_task);
      const unsigned int finish = start + duration_task;

      if (finish < bestFinish) {
        bestFinish = finish;
        bestProc = PE;
        bestStart = start;
        bestTransfers = transfers;
      } else if (finish == bestFinish) {
        if (coin(local_rng)) {
          bestFinish = finish;
          bestProc = PE;
          bestStart = start;
          bestTransfers = transfers;
        }
      }
    }

    if (bestProc == UINT_MAX || bestFinish == UINT_MAX) {
      throw std::runtime_error("No feasible processor found for task " + std::to_string(task) + " in guarantee_deadline.");
    }

    final_processor_of_task[task] = bestProc;
    final_schedule.assign[task] = {static_cast<int>(bestProc), bestStart, bestFinish};
    final_start_and_end_times[task] = {bestStart, bestFinish};
    final_processors[(size_t)bestProc].insert_interval(bestStart, bestFinish);
    if (bestFinish > final_makespan) final_makespan = bestFinish;

    for (const auto& transfer : bestTransfers) {
      final_links[(size_t)transfer.link_id].insert_interval(transfer.start_time, transfer.end_time);
      final_schedule.messages[transfer.id] = Transfer_details{transfer.link_id, transfer.start_time, transfer.end_time};
    }
  }
  // Now we should have a completed final schedule
  if (!final_correctness()) {
    throw std::runtime_error("Final schedule is incorrect in guarantee_deadline.");
  }

  // compute makespan
  unsigned int final_computed_makespan = 0;
  for (unsigned int task = 0; task < G.getNumNodes(); ++task) {
    if (final_start_and_end_times[task].second > final_computed_makespan) {
      final_computed_makespan = final_start_and_end_times[task].second;
    }
  }
}

bool CaWoMap::final_correctness() {
  bool ok = true;
  auto link_id = [this](unsigned int source, unsigned int target) {
    return source + target * _config.getNumProcessors();
  };

  // --- 1. Check predecessor constraints ---
  for (size_t task = 0; task < G.getNumNodes(); ++task) {
    unsigned int task_start = final_start_and_end_times[task].first;
    for (const auto& pred : G.adjList_inNeighbors[task]) {
      unsigned int pred_id = pred.id;
      unsigned int pred_finish = final_start_and_end_times[pred_id].second;

      // check for communications if on different processors
      if (final_processor_of_task[task] == final_processor_of_task[pred_id]) {
        if (pred_finish > task_start) {
          std::cout << "Predecessor constraint violated: Task " << task << " starts at " << task_start << " before predecessor " << pred_id << " finishes at " << pred_finish << " on same processor.\n";
          ok = false;
          return false;
        }
      } else {
        // now we also have to check the message transfer
        uint64_t msg_id = make_message_id(
          (uint16_t)pred_id,
          (uint16_t)task,
          (uint16_t)link_id(final_processor_of_task[pred_id], final_processor_of_task[task]),
          (uint16_t)final_processor_of_task[task]
        );

        Transfer_details msg_transfer = final_schedule.messages.at(msg_id);
        // check that message starts not too early and does not end too late
        if (msg_transfer.start_time < pred_finish) {
          std::cout << "Message transfer for task " << task << " from predecessor " << pred_id << " starts too early at " << msg_transfer.start_time << " before predecessor finishes at " << pred_finish << ".\n";
          ok = false;
          return false;
        }
        if (msg_transfer.end_time > task_start) {
          std::cout << "Message transfer for task " << task << " from predecessor " << pred_id << " ends too late at " << msg_transfer.end_time << " after task starts at " << task_start << ".\n";
          ok = false;
          return false;
        }
      }
    }
  }

  // --- 2. Check that the tasks do not overlap on the same processor ---
  for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
    std::vector<std::pair<unsigned int, unsigned int>> intervals;
    for (size_t task = 0; task < G.getNumNodes(); ++task) {
      if (final_processor_of_task[task] == p) {
        intervals.push_back(final_start_and_end_times[task]);
      }
    }
    // sort intervals by start time
    std::sort(intervals.begin(), intervals.end(), [](const auto& a, const auto& b) {
      return a.first < b.first;
    });
    // check for overlaps
    for (size_t i = 1; i < intervals.size(); ++i) {
      if (intervals[i].first < intervals[i-1].second) {
        std::cout << "Overlap detected on processor " << p << " between intervals [" << intervals[i-1].first << ", " << intervals[i-1].second << ") and [" << intervals[i].first << ", " << intervals[i].second << ").\n";
        ok = false;
        return false;
      }
    }
  }

  // use CWM_schedule messages to check for overlaps
  for (size_t l = 0; l < final_links.size(); ++l) {
    std::vector<std::pair<unsigned int, unsigned int>> intervals;
    for (const auto& [msg_id, details] : final_schedule.messages) {
      if (details.link_id == l) {
        intervals.push_back({details.start_time, details.end_time});
      }
    }
    // sort intervals by start time
    std::sort(intervals.begin(), intervals.end(), [](const auto& a, const auto& b) {
      return a.first < b.first;
    });
    // check for overlaps
    for (size_t i = 1; i < intervals.size(); ++i) {
      if (intervals[i].first < intervals[i-1].second) {
        std::cout << "Overlap detected on communication link " << l << " between intervals [" << intervals[i-1].first << ", " << intervals[i-1].second << ") and [" << intervals[i].first << ", " << intervals[i].second << ").\n";
        ok = false;
        return false;
      }
    }
  }

  return ok;
}

unsigned int CaWoMap::covers_how_many(unsigned int start, unsigned int end) {
  unsigned int interval_id = 0;
  auto it = interval_map.upper_bound(start);
  if (it != interval_map.begin()) {
    --it;
    interval_id = it->second.interval_id;
  }
  unsigned int interval_counter = 1;
  while (end > _config.getIntervals()[interval_id+1]) {
    interval_counter++;
    interval_id++;
  }
  return interval_counter;
}

void CaWoMap::find_choice(
  const unsigned int& task,
  choice& bestChoice,
  Job& current_job,
  std::vector<unsigned int>& arrivals,
  std::vector<Transfer>& transfers,
  std::vector<PE>& current_PE_subset,
  unsigned int not_earlier_than
) {
  auto link_id = [this](unsigned int source, unsigned int target) {
    return source + target * _config.getNumProcessors();
  };

  bestChoice.bestStart = UINT_MAX;
  bestChoice.bestFinish = UINT_MAX;
  bestChoice.bestProc = UINT_MAX;
  bestChoice.bestTransfers.clear();
  for (const auto& PE : current_PE_subset) {
    arrivals.clear(); arrivals.reserve(current_job.preds.size());
    transfers.clear(); transfers.reserve(current_job.preds.size());

    bool feasible = true;

    std::vector<IntervalSet> temp_links(CWM_links.size());
    std::vector<bool> touched(CWM_links.size(), false);

    for (const auto& predecessor : current_job.preds) {
      unsigned int pred_id = predecessor.pred;
      unsigned int pred_proc = processor_of_task[pred_id];

      if (pred_proc == UINT_MAX) {
        feasible = false;
        std::cout << "This should not happen" << std::endl;
        break; // predecessor not scheduled yet
      }
      const unsigned int finishTime_pred = start_and_end_times[pred_id].second;

      if (pred_proc == PE) {
        arrivals.push_back(finishTime_pred);
        continue;
      } else {
        const unsigned int link_ID = link_id(pred_proc, PE);
        IntervalSet& link_temp = temp_links[(size_t)link_ID];

        if (!touched[(size_t)link_ID]) {
          if (!CWM_links[(size_t)link_ID].intervals.empty()) {
            link_temp.intervals = CWM_links[(size_t)link_ID].intervals;
          }
          touched[(size_t)link_ID] = true;
        }

        unsigned int start = finishTime_pred;
        start = link_temp.earliest_gap(start, predecessor.msg_size);
        unsigned int end = start + predecessor.msg_size;

        uint64_t msg_id = make_message_id(
          (uint16_t)pred_id,
          (uint16_t)task,
          (uint16_t)link_ID,
          (uint16_t)PE
        );

        arrivals.push_back(end);
        transfers.push_back({link_ID, start, end, msg_id});
        temp_links[(size_t)link_ID].insert_interval(start, end);
      }
    }
    if (not_earlier_than > 0) arrivals.push_back(not_earlier_than); 
    if (!feasible) continue;

    const unsigned int avail = arrivals.empty()
      ? 0
      : *std::max_element(arrivals.begin(), arrivals.end());

    const unsigned int duration_task = running_times[task][PE];
    const unsigned int start = CWM_processors[(size_t)PE].earliest_gap(avail, duration_task);
    const unsigned int finish = start + duration_task;
  

    if (finish < bestChoice.bestFinish) {
      bestChoice.bestFinish = finish;
      bestChoice.bestProc = PE;
      bestChoice.bestStart = start;
      bestChoice.bestTransfers = transfers;
    } else if (finish == bestChoice.bestFinish) {
      // coin flip to break ties
      if (flipper.flip()) {
        bestChoice.bestFinish = finish;
        bestChoice.bestProc = PE;
        bestChoice.bestStart = start;
        bestChoice.bestTransfers = transfers;
      }
    }
  }
}

unsigned int CaWoMap::compute_EST_without_communications(unsigned int task) {
  unsigned int EST = 0;
  for (const auto& pred : G.adjList_inNeighbors[task]) {
    unsigned int pred_id = pred.id;
    unsigned int pred_finish = start_and_end_times[pred_id].second;
    if (pred_finish > EST) {
      EST = pred_finish;
    }
  }
  return EST;
}

bool CaWoMap::CWM_correctness() {
  bool ok = true;
  auto link_id = [this](unsigned int source, unsigned int target) {
    return source + target * _config.getNumProcessors();
  };

  // --- 1. Check predecessor constraints ---
  for (size_t task = 0; task < G.getNumNodes(); ++task) {
    unsigned int task_start = start_and_end_times[task].first;
    for (const auto& pred : G.adjList_inNeighbors[task]) {
      unsigned int pred_id = pred.id;
      unsigned int pred_finish = start_and_end_times[pred_id].second;
      
      // check for communications if on different processors
      if (processor_of_task[task] == processor_of_task[pred_id]) {
        if (pred_finish > task_start) {
          std::cout << "Predecessor constraint violated: Task " << task << " starts at " << task_start << " before predecessor " << pred_id << " finishes at " << pred_finish << " on same processor.\n";
          ok = false;
          return false;
        }
      } else {
        // now we also have to check the message transfer
        uint64_t msg_id = make_message_id(
          (uint16_t)pred_id,
          (uint16_t)task,
          (uint16_t)link_id(processor_of_task[pred_id], processor_of_task[task]),
          (uint16_t)processor_of_task[task]
        );
        
        Transfer_details msg_transfer = CWM_schedule.messages.at(msg_id);
        // check that message starts not too early and does not end too late
        if (msg_transfer.start_time < pred_finish) {
          std::cout << "Message transfer for task " << task << " from predecessor " << pred_id << " starts too early at " << msg_transfer.start_time << " before predecessor finishes at " << pred_finish << ".\n";
          ok = false;
          return false;
        }
        if (msg_transfer.end_time > task_start) {
          std::cout << "Message transfer for task " << task << " from predecessor " << pred_id << " ends too late at " << msg_transfer.end_time << " after task starts at " << task_start << ".\n";
          ok = false;
          return false;
        }
      }
    }
  }

  // --- 2. Check that the tasks do not overlap on the same processor ---
  for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
    std::vector<std::pair<unsigned int, unsigned int>> intervals;
    for (size_t task = 0; task < G.getNumNodes(); ++task) {
      if (processor_of_task[task] == p) {
        intervals.push_back(start_and_end_times[task]);
      }
    }
    // sort intervals by start time
    std::sort(intervals.begin(), intervals.end(), [](const auto& a, const auto& b) {
      return a.first < b.first;
    });
    // check for overlaps
    for (size_t i = 1; i < intervals.size(); ++i) {
      if (intervals[i].first < intervals[i-1].second) {
        std::cout << "Overlap detected on processor " << p << " between intervals [" << intervals[i-1].first << ", " << intervals[i-1].second << ") and [" << intervals[i].first << ", " << intervals[i].second << ").\n";
        ok = false;
        return false;
      }
    }
  }

  // use CWM_schedule messages to check for overlaps
  for (size_t l = 0; l < CWM_links.size(); ++l) {
    std::vector<std::pair<unsigned int, unsigned int>> intervals;
    for (const auto& [msg_id, details] : CWM_schedule.messages) {
      if (details.link_id == l) {
        intervals.push_back({details.start_time, details.end_time});
      }
    }
    // sort intervals by start time
    std::sort(intervals.begin(), intervals.end(), [](const auto& a, const auto& b) {
      return a.first < b.first;
    });
    // check for overlaps
    for (size_t i = 1; i < intervals.size(); ++i) {
      if (intervals[i].first < intervals[i-1].second) {
        std::cout << "Overlap detected on communication link " << l << " between intervals [" << intervals[i-1].first << ", " << intervals[i-1].second << ") and [" << intervals[i].first << ", " << intervals[i].second << ").\n";
        ok = false;
        return false;
      }
    }
  }

  return ok;
}

void CaWoMap::prepare_processor_subsets(double offset) {
  all_processor_subsets.resize((_config.getIntervals().size() - 1)); 
  for (size_t interval_id = 0; interval_id < _config.getIntervals().size() - 1; ++interval_id) {
    budget powerBudget = _config.getBudgets()[interval_id];
    all_processor_subsets[interval_id] = compute_processor_subset(powerBudget, offset);
    if (all_processor_subsets[interval_id].size() == 0) {std::cout << "EMPTY PROCESSOR SUBSET" << std::endl;}
  }
}

unsigned int CaWoMap::getIntervalId(unsigned int time) {
  unsigned int interval_id = 0; 

  auto it = interval_map.upper_bound(time); // first interval with start > time 
  if (it != interval_map.begin()) {
    --it;
    interval_id = it->second.interval_id;
  }
  return interval_id;
}

bool CaWoMap::HEFT_correctness() {
  // check correctness of the HEFT schedule
  bool ok = true;

  auto link_id = [this](unsigned int source, unsigned int target) {
    return source + target * _config.getNumProcessors();
  };

  // --- 1. Check predecessor constraints ---
  for (size_t task = 0; task < G.getNumNodes(); ++task) {
    unsigned int task_start = heft_start_and_end_times[task].first;
    for (const auto& pred : G.adjList_inNeighbors[task]) {
      unsigned int pred_id = pred.id;
      unsigned int pred_finish = heft_start_and_end_times[pred_id].second;
      
      // check for communications if on different processors
      if (heft_processor_of_task[task] == heft_processor_of_task[pred_id]) {
        if (pred_finish > task_start) {
          std::cout << "Predecessor constraint violated: Task " << task << " starts at " << task_start << " before predecessor " << pred_id << " finishes at " << pred_finish << " on same processor.\n";
          ok = false;
          return false;
        }
      } else {
        // now we also have to check the message transfer
        uint64_t msg_id = make_message_id(
          (uint16_t)pred_id,
          (uint16_t)task,
          (uint16_t)link_id(heft_processor_of_task[pred_id], heft_processor_of_task[task]),
          (uint16_t)heft_processor_of_task[task]
        );
        
        Transfer_details msg_transfer = HEFT_schedule.messages.at(msg_id);
        // check that message starts not too early and does not end too late
        if (msg_transfer.start_time < pred_finish) {
          std::cout << "Message transfer for task " << task << " from predecessor " << pred_id << " starts too early at " << msg_transfer.start_time << " before predecessor finishes at " << pred_finish << ".\n";
          ok = false;
          return false;
        }
        if (msg_transfer.end_time > task_start) {
          std::cout << "Message transfer for task " << task << " from predecessor " << pred_id << " ends too late at " << msg_transfer.end_time << " after task starts at " << task_start << ".\n";
          ok = false;
          return false;
        }
      }
    }
  }

  // --- 2. Check that the tasks do not overlap on the same processor ---
  for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
    std::vector<std::pair<unsigned int, unsigned int>> intervals;
    for (size_t task = 0; task < G.getNumNodes(); ++task) {
      if (heft_processor_of_task[task] == p) {
        intervals.push_back(heft_start_and_end_times[task]);
      }
    }
    // sort intervals by start time
    std::sort(intervals.begin(), intervals.end(), [](const auto& a, const auto& b) {
      return a.first < b.first;
    });
    // check for overlaps
    for (size_t i = 1; i < intervals.size(); ++i) {
      if (intervals[i].first < intervals[i-1].second) {
        std::cout << "Overlap detected on processor " << p << " between intervals [" << intervals[i-1].first << ", " << intervals[i-1].second << ") and [" << intervals[i].first << ", " << intervals[i].second << ").\n";
        ok = false;
        return false;
      }
    }
  }

  // --- 3. Check that the communication links do not overlap ---
  for (auto& interval_set : links) {
    if (interval_set.intervals.empty()) continue;

    auto it = interval_set.intervals.begin();
    auto prev = it++;
    for (; it != interval_set.intervals.end(); ++it, ++prev) {
        const auto& [a, b] = *prev;
        const auto& [c, d] = *it;

        // Must have positive-length intervals
        if (a >= b) return false;

        // Must not overlap or touch
        if (b > c) return false;
    }
  }

  return ok;
}

void CaWoMap::printDAG() {
  // print DAG
  std::cout << "Number of nodes: " << G.getNumNodes() << std::endl;
  std::cout << "Node weights: " << std::endl;
  for (size_t i = 0; i < G.nodeWeights.size(); i++) {
    std::cout << "Node " << i << ": " << G.nodeWeights[i] << std::endl;
  }
  std::cout << "Adjacency list (out): " << std::endl;
  for (size_t i = 0; i < G.adjList_outNeighbors.size(); i++) {
    std::cout << i << ": ";
    for (const auto& neighbor : G.adjList_outNeighbors[i]) {
      std::cout << neighbor.id << " (" << neighbor.weight << ") ";
    }
    std::cout << std::endl;
  }
}

std::vector<PE> CaWoMap::compute_processor_subset(const budget powerBudget, double offset) {
  const std::vector<power>& PWork = _config.getPWork();
  const std::vector<unsigned int>& speed = _config.getSpeed();
  const unsigned int numProcessors = _config.getNumProcessors();
  std::vector<PE> processorSet;

  unsigned int base_power = _config.getBasePower();

  power min_working_power = INT_MAX;
  PE min_working_power_processor = INT_MAX;
  unsigned int counter = 0;
  for (auto pw : PWork) {
    if (pw < min_working_power) {
      min_working_power = pw;
      min_working_power_processor = counter++; 
    } 
  }

  unsigned int cap = (powerBudget > base_power) ? powerBudget-base_power : 0;
  if (cap == 0) {
    processorSet.push_back(min_working_power_processor);
    return processorSet;
  }

  if (offset != 0.0) {cap = static_cast<unsigned int>(std::round((1-offset) * cap)); }

  std::vector<std::vector<unsigned int>> dp(numProcessors + 1, std::vector<unsigned int>(cap + 1, 0)); 

  for (unsigned int i = 1; i < numProcessors + 1; i++) {
    for (unsigned int j = min_working_power; j < cap + 1; j++) {
      unsigned int max_with_pick = 0;
      if (PWork[i-1] <= j) {
        max_with_pick = speed[i-1] + dp[i-1][j - PWork[i-1]];
      }
      unsigned int max_without_pick = dp[i-1][j];
      dp[i][j] = (max_with_pick > max_without_pick) ? max_with_pick : max_without_pick;
    }
  }

  // compute selected processors on the way
  unsigned int i = numProcessors;
  unsigned int j = cap;
  while (i > 0 && j > 0) {
    if (dp[i][j] != dp[i-1][j]) {
      processorSet.push_back(i-1); // processor numbering starting from 0
      j = j - PWork[i-1]; 
    }
    i = i-1;
  }

  if (processorSet.size() == 0) {
    // add the processor with the least dynamic power
    processorSet.push_back(min_working_power_processor);
  }
  return processorSet;
}

void CaWoMap::compute_topological_order(std::vector<unsigned int>& topological_order) {
  topological_order.clear();

  std::vector<int> in_degree(G.getNumNodes(), 0);
  for (size_t i = 0; i < G.getNumNodes(); ++i) {
    in_degree[i] = G.adjList_inNeighbors[i].size();
  }
  std::queue<int> zero_in_degree;
  for (size_t i = 0; i < in_degree.size(); ++i) {
    if (in_degree[i] == 0) {
      zero_in_degree.push(i);
    }
  }

  while(!zero_in_degree.empty()) {
    unsigned int current_node = zero_in_degree.front();
    zero_in_degree.pop();
    topological_order.push_back(current_node);

    for (const auto& neighbor : G.adjList_outNeighbors[current_node]) {
      in_degree[neighbor.id]--;
      if (in_degree[neighbor.id] == 0) {
        zero_in_degree.push(neighbor.id);
      }
    }
  }
  assert(topological_order.size() == G.getNumNodes() && "Topological sort failed, graph might have cycles.");
}

unsigned int CaWoMap::get_running_time(unsigned int task, PE P) {
  // We always round up the running time to the next integer. Argument: you always have to pay for the whole time unit.
  float time = static_cast<float>(G.nodeWeights[task]) / static_cast<float>(_config.getSpeed()[P]);
  return static_cast<unsigned int>(std::ceil(time));
}

void CaWoMap::compute_avg_comp_cost(std::vector<float>& avg_comp_cost) {
  for (size_t i = 0; i < G.getNumNodes(); ++i) {
    float total_cost = 0.0f;
    for (const auto& speed : _config.getSpeed()) {
      total_cost += static_cast<float>(G.nodeWeights[i]) / static_cast<float>(speed);
    }
    avg_comp_cost[i] = total_cost / static_cast<float>(_config.getSpeed().size());
  }
}

void CaWoMap::compute_upward_ranks(std::vector<float>& upward_rank, std::vector<unsigned int>& topological_order) {
  std::vector<float> avg_comp_cost(G.getNumNodes(), 0.0f);
  compute_avg_comp_cost(avg_comp_cost);

  for (const auto& node : topological_order) {
    upward_rank[node] = avg_comp_cost[node];
    float max_contribution = 0.0f;
    for (const auto& neighbor : G.adjList_outNeighbors[node]) {
      max_contribution = std::max(max_contribution, static_cast<float>(neighbor.weight) + upward_rank[neighbor.id]);
    }
    upward_rank[node] += max_contribution;
  }
}

void CaWoMap::printMappingForCaWoSched() {
  std::cout << _config.getNumProcessors() << std::endl;
  std::vector<std::vector<unsigned int>> HEFTmapping(_config.getNumProcessors());
  for (size_t i = 0; i < G.getNumNodes(); ++i) {
    HEFTmapping[heft_processor_of_task[i]].push_back(i);
  }

  for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
    // sort the tasks on the processors
    std::sort(HEFTmapping[p].begin(), HEFTmapping[p].end(), [this] (const Task& a, const Task& b) {
      return heft_start_and_end_times[a].first < heft_start_and_end_times[b].first;
    });
    for (size_t j = 0; j < HEFTmapping[p].size(); ++j) {
      if (j != HEFTmapping[p].size() - 1) {
        std::cout << HEFTmapping[p][j] << " ";
      } else {
        std::cout << HEFTmapping[p][j];
      }
    }
    std::cout << std::endl; 
  }
}

void CaWoMap::printSetupForCaWoSched(unsigned int deadline) {

  // find the first interval that intersects with the makespan
  unsigned int interval_index = 0;
  for (unsigned int i = 0; i < _config.getIntervals().size() -1; ++i) {
    if (_config.getIntervals()[i] <= deadline && deadline <= _config.getIntervals()[i + 1]) {
      interval_index = i;
      break;
    }
  }
  std::cout << interval_index + 1 << std::endl; // this is the number of intervals that we have

  // print all idle powers 
  for (size_t i = 0; i < _config.getPIdle().size(); ++i) {
    std::cout << _config.getPIdle()[i] << " ";
  }
  for (size_t i = 0; i < _config.getPIdleComm().size(); ++i) {
    if (i != _config.getPIdleComm().size() - 1) {
      std::cout << _config.getPIdleComm()[i] << " ";
    } else {
      std::cout << _config.getPIdleComm()[i] << std::endl;
    }
  }

    // print all work powers 
  for (size_t i = 0; i < _config.getPWork().size(); ++i) {
    std::cout << _config.getPWork()[i] << " ";
  }
  for (size_t i = 0; i < _config.getPWorkComm().size(); ++i) {
    if (i != _config.getPWorkComm().size() - 1) {
      std::cout << _config.getPWorkComm()[i] << " ";
    } else {
      std::cout << _config.getPWorkComm()[i] << std::endl;
    }
  }
  
  std::cout << "1" << std::endl; // this is the current carbon cost

  for (size_t i = 0; i <= interval_index; ++i) {
    std::cout << _config.getBudgets()[i] << " ";
  }
  std::cout << std::endl;

  for (size_t i = 0; i <= interval_index+1; ++i) {
    if (i != interval_index+1) {
      std::cout << _config.getIntervals()[i] << " ";
    } else {
      std::cout << deadline << std::endl;
    }
  }
}

void CaWoMap::include_later_tasks_in_interval(unsigned int task, unsigned int interval_end, std::vector<unsigned int>& later_tasks) {
  // compute all successors of task 
  std::queue<unsigned int> to_process;
  std::vector<bool> visited(G.getNumNodes(), false);
  to_process.push(task);
  visited[task] = true;
  while (!to_process.empty()) {
    unsigned int current_task = to_process.front();
    to_process.pop();

    for (const auto& succ : G.adjList_outNeighbors[current_task]) {
      unsigned int succ_id = succ.id;
      if (!visited[succ_id]) {
        // if the start time is within the interval, include it
        if (start_and_end_times[succ_id].first < interval_end) {
          later_tasks.push_back(succ_id);
          to_process.push(succ_id);
          visited[succ_id] = true;
        }
        to_process.push(succ_id);
      }
    }
  }
}

void CaWoMap::prevent_overlaps_in_later_tasks(const unsigned int task_to_move, std::vector<unsigned int>& later_tasks) {
  /*
  * For each processor: if one task is in later tasks, all succeeding tasks on the same processor must also be included
  */

  std::vector<bool> is_in_later_tasks(G.getNumNodes(), false);
  is_in_later_tasks[task_to_move] = true;
  for (const auto& t : later_tasks) {
    is_in_later_tasks[t] = true;
  }

  // Store the tasks on each processor and sort them by start time
  std::vector<std::vector<unsigned int>> tasks_on_processor(_config.getNumProcessors());
  for (size_t t = 0; t < G.getNumNodes(); ++t) {
    unsigned int p = processor_of_task[t];
    tasks_on_processor[p].push_back(t);
  }
  for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
    std::sort(tasks_on_processor[p].begin(), tasks_on_processor[p].end(), [this](unsigned int a, unsigned int b) {
      return start_and_end_times[a].first < start_and_end_times[b].first;
    });
  }

  bool found = false;
  // Now iterate over each processor
  for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
    found = false;
    for (const auto& t : tasks_on_processor[p]) {
      if (is_in_later_tasks[t]) {
        found = true;
        continue;
      }
      if (found) {
        if (!is_in_later_tasks[t]) {
          later_tasks.push_back(t);
          is_in_later_tasks[t] = true;
        }
      }
    }
  }
}

void CaWoMap::prevent_overlaps_in_channels(std::vector<std::pair<uint64_t, Transfer_details>>& affected_messages) {
/*
* This is now the same idea as for the tasks, but for the messages on each channel
*/

  std::set<uint64_t> affected_message_ids;
  for (const auto& [msg_id, details] : affected_messages) {
    affected_message_ids.insert(msg_id);
  }

  // Store the messages on each link and sort them by start time
  std::vector<std::vector<std::pair<uint64_t, Transfer_details>>> messages_on_link(CWM_links.size());
  for (const auto& [msg_id, details] : CWM_schedule.messages) {
    messages_on_link[details.link_id].push_back({msg_id, details});
  }
  for (size_t l = 0; l < CWM_links.size(); ++l) {
    std::sort(messages_on_link[l].begin(), messages_on_link[l].end(), [](const auto& a, const auto& b) {
      return a.second.start_time < b.second.start_time;
    });
  }

  bool found = false;
  // Now iterate over each link
  for (size_t l = 0; l < CWM_links.size(); ++l) {
    found = false;
    for (const auto& [msg_id, details] : messages_on_link[l]) {
      if (affected_message_ids.find(msg_id) != affected_message_ids.end()) {
        found = true;
        continue;
      }
      if (found) {
        if (affected_message_ids.find(msg_id) == affected_message_ids.end()) {
          affected_messages.push_back({msg_id, details});
          affected_message_ids.insert(msg_id);
        }
      }
    }
  }
}

void CaWoMap::include_later_tasks_in_interval_final(unsigned int task, unsigned int interval_end, std::vector<unsigned int>& later_tasks) {
  // compute all successors of task 
  std::queue<unsigned int> to_process;
  std::vector<bool> visited(G.getNumNodes(), false);
  to_process.push(task);
  visited[task] = true;
  while (!to_process.empty()) {
    unsigned int current_task = to_process.front();
    to_process.pop();

    for (const auto& succ : G.adjList_outNeighbors[current_task]) {
      unsigned int succ_id = succ.id;
      if (!visited[succ_id]) {
        // if the start time is within the interval, include it
        if (final_start_and_end_times[succ_id].first < interval_end) {
          later_tasks.push_back(succ_id);
          to_process.push(succ_id);
          visited[succ_id] = true;
        }
        to_process.push(succ_id);
      }
    }
  }
}

void CaWoMap::prevent_overlaps_in_later_tasks_final(const unsigned int task_to_move, std::vector<unsigned int>& later_tasks) {
  /*
  * For each processor: if one task is in later tasks, all succeeding tasks on the same processor must also be included
  */

  std::vector<bool> is_in_later_tasks(G.getNumNodes(), false);
  is_in_later_tasks[task_to_move] = true;
  for (const auto& t : later_tasks) {
    is_in_later_tasks[t] = true;
  }

  // Store the tasks on each processor and sort them by start time
  std::vector<std::vector<unsigned int>> tasks_on_processor(_config.getNumProcessors());
  for (size_t t = 0; t < G.getNumNodes(); ++t) {
    unsigned int p = final_processor_of_task[t];
    tasks_on_processor[p].push_back(t);
  }
  for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
    std::sort(tasks_on_processor[p].begin(), tasks_on_processor[p].end(), [this](unsigned int a, unsigned int b) {
      return final_start_and_end_times[a].first < final_start_and_end_times[b].first;
    });
  }

  bool found = false;
  // Now iterate over each processor
  for (size_t p = 0; p < _config.getNumProcessors(); ++p) {
    found = false;
    for (const auto& t : tasks_on_processor[p]) {
      if (is_in_later_tasks[t]) {
        found = true;
        continue;
      }
      if (found) {
        if (!is_in_later_tasks[t]) {
          later_tasks.push_back(t);
          is_in_later_tasks[t] = true;
        }
      }
    }
  }
}

void CaWoMap::prevent_overlaps_in_channels_final(std::vector<std::pair<uint64_t, Transfer_details>>& affected_messages) {
/*
* This is now the same idea as for the tasks, but for the messages on each channel
*/

  std::set<uint64_t> affected_message_ids;
  for (const auto& [msg_id, details] : affected_messages) {
    affected_message_ids.insert(msg_id);
  }

  // Store the messages on each link and sort them by start time
  std::vector<std::vector<std::pair<uint64_t, Transfer_details>>> messages_on_link(CWM_links.size());
  for (const auto& [msg_id, details] : final_schedule.messages) {
    messages_on_link[details.link_id].push_back({msg_id, details});
  }
  for (size_t l = 0; l < final_links.size(); ++l) {
    std::sort(messages_on_link[l].begin(), messages_on_link[l].end(), [](const auto& a, const auto& b) {
      return a.second.start_time < b.second.start_time;
    });
  }

  bool found = false;
  // Now iterate over each link
  for (size_t l = 0; l < final_links.size(); ++l) {
    found = false;
    for (const auto& [msg_id, details] : messages_on_link[l]) {
      if (affected_message_ids.find(msg_id) != affected_message_ids.end()) {
        found = true;
        continue;
      }
      if (found) {
        if (affected_message_ids.find(msg_id) == affected_message_ids.end()) {
          affected_messages.push_back({msg_id, details});
          affected_message_ids.insert(msg_id);
        }
      }
    }
  }
}
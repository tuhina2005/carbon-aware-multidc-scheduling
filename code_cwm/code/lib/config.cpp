#include <config.hpp>
#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

void SchedulerConfig::printConfig() const {
    std::cout << "Scheduler Configuration:\n";
    std::cout << "  DAG File: " << dagFile << "\n";
    std::cout << "  Mapping File: " << mappingFile << "\n";
    std::cout << "  Cluster Setup File: " << clusterSetupFile << "\n";
    std::cout << "  Cluster Variant: " << clusterVariant << "\n";
    std::cout << "  Profile File: " << profileFile << "\n";
    std::cout << "  The following is extracted from the profile file:\n";
    std::cout << "  Time Horizon: " << timeHorizon      << "\n";
    std::cout << "  Number of Intervals: " << numberOfIntervals << "\n";
    std::cout << "  Intervals: ";
    for (const auto& interval : intervals) {
        std::cout << interval << " ";
    }
    std::cout << "\n";
    std::cout << "  Budgets: ";
    for (const auto& budget : budgets) {
        std::cout << budget << " ";
    }
    std::cout << "\n";
}

void SchedulerConfig::parseProfile() {

    const std::string profilePath = getProfileFile();
    if (profilePath.empty()) {
        std::cerr << "Profile file not set. Skipping profile parsing.\n";
        return;
    }

    std::ifstream file(profilePath);
    if (!file.is_open()) {
        std::cerr << "Failed to open profile file: " << profilePath << "\n";
        return;
    }

    // parse the json file 
    json profile;
    file >> profile;

    unsigned int horizon = profile["horizon"];
    setTimeHorizon(horizon);

    unsigned int numberOfIntervals = profile["number_of_intervals"];
    setNumberOfIntervals(numberOfIntervals);

    const std::vector<unsigned int> intervals = profile["intervals"].get<std::vector<unsigned int>>();
    setIntervals(intervals);

    const std::vector<unsigned int> budgets = profile["budgets"].get<std::vector<unsigned int>>();
    if (budgets.size() != numberOfIntervals) {
        std::cerr << "Mismatch in number of intervals and budgets in profile file.\n";
        return;
    }
    setBudgets(budgets);
}

void SchedulerConfig::parseClusterSetup() {
    const std::string clusterPath = getClusterSetupFile();
    if (clusterPath.empty()) {
        std::cerr << "Cluster setup file not set. Skipping cluster setup parsing.\n";
        return;
    }

    std::ifstream file(clusterPath);
    if (!file.is_open()) {
        std::cerr << "Failed to open cluster setup file: " << clusterPath << "\n";
        return;
    }

    // parse the json file 
    json clusterSetup;
    file >> clusterSetup;

    // Read processor types
    const std::string variant = getClusterVariant();
    if (variant.empty()) {
        std::cerr << "Cluster variant not set. Skipping cluster setup parsing.\n";
        return; 
    } 

    unsigned int numTypes = clusterSetup["number_of_processor_types"];

    std::vector<processorType> processorTypes;
    for (const auto& proc : clusterSetup["processors"]) {
        processorType PE;
        PE.speed = proc["speed_value"];
        PE.idlePower = proc["idle_power"];
        PE.workPower = proc["work_power"];
        processorTypes.push_back(PE);
    }

    for (const auto& cluster : clusterSetup["clusters"]) {
        if (cluster["cluster_id"] == variant) {
            unsigned int numPEsPerType = cluster["processors_per_type"];
            PIdle.clear();
            PWork.clear();
            Speed.clear();
            Speed.resize(numTypes * numPEsPerType);
            PIdle.resize(numTypes * numPEsPerType);
            PWork.resize(numTypes * numPEsPerType);
            for (unsigned int i = 0; i < numTypes; ++i) {
                for (unsigned int j = 0; j < numPEsPerType; ++j) {
                    PIdle[i * numPEsPerType + j] = processorTypes[i].idlePower;
                    PWork[i * numPEsPerType + j] = processorTypes[i].workPower;
                    Speed[i * numPEsPerType + j] = processorTypes[i].speed;
                }
            }
            std::vector<unsigned int> PIdle_comm = cluster["communication_idle_powers"].get<std::vector<unsigned int>>(); 
            std::vector<unsigned int> PWork_comm = cluster["communication_work_powers"].get<std::vector<unsigned int>>();

            setPIdleComm(PIdle_comm);
            setPWorkComm(PWork_comm);
        }
    }

    setNumProcessors(PIdle.size());
}

void SchedulerConfig::setBasePower() {
    unsigned int totalIdlePower = 0;
    for (const auto& p : PIdle) {
        totalIdlePower += p;
    }
    for (const auto& p : PIdle_comm) {
        totalIdlePower += p;
    }
    basePower = totalIdlePower;
}


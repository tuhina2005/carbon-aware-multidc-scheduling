#pragma once

#include <string>
#include <unordered_map>
#include <vector>
#include <memory>
#include <iostream>
#include <fstream>
#include <sstream>
#include <random>

struct processorType {
    unsigned int speed{};
    unsigned int idlePower{};
    unsigned int workPower{};
};

class SchedulerConfig {
public:

    SchedulerConfig() = default;

    // Singleton instance getter
    static SchedulerConfig& getInstance() {
        static SchedulerConfig instance;
        return instance;
    }

    // Prevent copying
    SchedulerConfig(const SchedulerConfig&) = delete;
    SchedulerConfig& operator=(const SchedulerConfig&) = delete;
    
    // Print current configuration
    void printConfig() const;

    
    // File paths
    const std::string& getDAGFile() const { return dagFile; }
    const std::string& getMappingFile() const { return mappingFile; }
    const std::string& getClusterSetupFile() const { return clusterSetupFile; }
    const std::string& getProfileFile() const { return profileFile; }

    const std::vector<unsigned int>& getIntervals() const { return intervals; }
    void setIntervals(const std::vector<unsigned int>& ints) { intervals = ints; }
    const std::vector<unsigned int>& getBudgets() const { return budgets; }
    void setBudgets(const std::vector<unsigned int>& buds) { budgets = buds; }
    const std::vector<unsigned int>& getPIdle() const { return PIdle; }
    void setPIdle(const std::vector<unsigned int>& pIdle) { PIdle = pIdle; }
    const std::vector<unsigned int>& getPWork() const { return PWork; }
    void setPWork(const std::vector<unsigned int>& pWork) { PWork = pWork; }
    const std::vector<unsigned int>& getSpeed() const { return Speed; }
    void setSpeed(const std::vector<unsigned int>& speed) { Speed = speed; }
    const std::vector<unsigned int>& getPIdleComm() const { return PIdle_comm; }
    void setPIdleComm(const std::vector<unsigned int>& pIdleComm) { PIdle_comm = pIdleComm; }
    const std::vector<unsigned int>& getPWorkComm() const { return PWork_comm; }
    void setPWorkComm(const std::vector<unsigned int>& pWorkComm) { PWork_comm = pWorkComm; }
    unsigned int getRandomSeed() const { return randomSeed; }
    void setRandomSeed(unsigned int seed) { randomSeed = seed; }

    // Power model parameters
    unsigned int getBasePower() const { return basePower; }
    void setBasePower();

    unsigned int getTimeHorizon() const { return timeHorizon; }
    unsigned int getNumberOfIntervals() const { return numberOfIntervals; }

    unsigned int getNumProcessors() const { return numProcessors; }
    
    std::string getClusterVariant() const { return clusterVariant; }
    
    void setDAGFile(const std::string& file) { dagFile = file; }
    void setMappingFile(const std::string& file) { mappingFile = file; }
    void setClusterSetupFileAndVariant(const std::string& file, const std::string& variant) { clusterSetupFile = file; clusterVariant = variant; }
    void setProfileFile(const std::string& file) { profileFile = file; }

    void setTimeHorizon(unsigned int horizon) { timeHorizon = horizon; }
    void setNumberOfIntervals(unsigned int intervals) { numberOfIntervals = intervals; }
    
    void setNumProcessors(unsigned int threads) { numProcessors = threads; }

    void parseProfile();
    void parseClusterSetup();
    void seedRNG(unsigned int seed) { rng.seed(seed);}

    void setDeadline(unsigned int deadline) { deadlineToMeet = deadline; }
    unsigned int getDeadline() { return deadlineToMeet; }

    std::mt19937 rng;
private:
    
    // File paths
    std::string dagFile;
    std::string mappingFile;
    std::string clusterSetupFile;
    std::string profileFile;
    std::string clusterVariant;
    
    // Algorithm parameters
    unsigned int timeHorizon;
    unsigned int numberOfIntervals;
    std::vector<unsigned int> intervals;
    std::vector<unsigned int> budgets;
    unsigned int deadlineToMeet;
    unsigned int numProcessors;

    // cluster data 
    std::vector<unsigned int> PIdle;
    std::vector<unsigned int> PWork;
    std::vector<unsigned int> Speed;
    unsigned int basePower;
    std::vector<unsigned int> PIdle_comm;
    std::vector<unsigned int> PWork_comm;

    unsigned int randomSeed;
};

// Convenience macro for accessing global config
#define CONFIG SchedulerConfig::getInstance()
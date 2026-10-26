#!/bin/bash
set -e

mapping_and_deadline=$(./../../../../code/deploy/heft_mapping $1 $2 $3 $4)
size="$3"
if [ "$3" = "small" ]; then
    profile_file="$4"
    profile_name=$(basename "$profile_file" .json)
    profile=""
    if [ "$profile_name" == "DE24s" ]; then
        profile="DE24"
    elif [ "$profile_name" == "LA24s" ]; then
        profile="LA24"
    fi
    DAG_file="$1"
    DAG=$(basename "$DAG_file" .dot)
    instance="${DAG}_small" 
    echo "$mapping_and_deadline" | sed '$d' > ../../instances/CaWoSched_Mappings/${instance}_${profile}_mapping.txt
    tight_deadline=$(echo "$mapping_and_deadline" | tail -n 1)
else
    profile_file="$4"
    profile_name=$(basename "$profile_file" .json)
    profile=""
    if [ "$profile_name" == "DE24l" ]; then
        profile="DE24"
    elif [ "$profile_name" == "LA24l" ]; then
        profile="LA24"
    fi
    DAG_file="$1"
    DAG=$(basename "$DAG_file" .dot)
    instance="${DAG}_large"
    echo "$mapping_and_deadline" | sed '$d' > ../../instances/CaWoSched_Mappings/${instance}_${profile}_mapping.txt
    tight_deadline=$(echo "$mapping_and_deadline" | tail -n 1)
fi

python3 adjust_rts_for_CaWoSched.py $1 ../../instances/CaWoSched_Mappings/${instance}_${profile}_mapping.txt ../../instances/CaWoSched_DAGs/${instance}_${profile}_DAG.dot

scaled12=$(echo "$tight_deadline * 1.2" | bc -l)
rounded12=$(echo "($scaled12+0.999)/1" | bc)
echo "$rounded12" > ../../instances/CaWoSched_Profiles/${instance}_${profile}_12_setup.txt
./../../../../code/deploy/setup_for_CaWoSched $1 $2 $3 $4 42 $rounded12 >> ../../instances/CaWoSched_Profiles/${instance}_${profile}_12_setup.txt
./../../../../../code_cawosched/deploy/multi_machine_scheduler ../../instances/CaWoSched_DAGs/${instance}_${profile}_DAG.dot ../../instances/CaWoSched_Mappings/${instance}_${profile}_mapping.txt ../../instances/CaWoSched_Profiles/${instance}_${profile}_12_setup.txt

scaled15=$(echo "$tight_deadline * 1.5" | bc -l)
rounded15=$(echo "($scaled15+0.999)/1" | bc)
echo "$rounded15" > ../../instances/CaWoSched_Profiles/${instance}_${profile}_15_setup.txt
./../../../../code/deploy/setup_for_CaWoSched $1 $2 $3 $4 42 $rounded15 >> ../../instances/CaWoSched_Profiles/${instance}_${profile}_15_setup.txt
./../../../../../code_cawosched/deploy/multi_machine_scheduler ../../instances/CaWoSched_DAGs/${instance}_${profile}_DAG.dot ../../instances/CaWoSched_Mappings/${instance}_${profile}_mapping.txt ../../instances/CaWoSched_Profiles/${instance}_${profile}_15_setup.txt

scaled20=$(echo "$tight_deadline * 2.0" | bc -l)
rounded20=$(echo "($scaled20+0.999)/1" | bc)
echo "$rounded20" > ../../instances/CaWoSched_Profiles/${instance}_${profile}_20_setup.txt
./../../../../code/deploy/setup_for_CaWoSched $1 $2 $3 $4 42 $rounded20 >> ../../instances/CaWoSched_Profiles/${instance}_${profile}_20_setup.txt
./../../../../../code_cawosched/deploy/multi_machine_scheduler ../../instances/CaWoSched_DAGs/${instance}_${profile}_DAG.dot ../../instances/CaWoSched_Mappings/${instance}_${profile}_mapping.txt ../../instances/CaWoSched_Profiles/${instance}_${profile}_20_setup.txt

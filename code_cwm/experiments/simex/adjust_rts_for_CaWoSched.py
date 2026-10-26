import numpy as np
import os 
import re
import argparse

def get_running_time(task_weight, processor, variant):
    if variant == "small":  
        if processor >= 0 and processor < 12: 
            return np.ceil(task_weight / 91).astype(int)
        elif processor >= 12 and processor < 24: 
            return np.ceil(task_weight / 93).astype(int)
        elif processor >= 24 and processor < 36: 
            return np.ceil(task_weight / 184).astype(int)
        elif processor >= 36 and processor < 48: 
            return np.ceil(task_weight / 254).astype(int)
        elif processor >= 48 and processor < 60: 
            return np.ceil(task_weight / 706).astype(int)
        elif processor >= 60 and processor < 72: 
            return np.ceil(task_weight / 581).astype(int)
    elif variant == "large":
        if processor >= 0 and processor < 24: 
            return np.ceil(task_weight / 91).astype(int)
        elif processor >= 24 and processor < 48: 
            return np.ceil(task_weight / 93).astype(int)
        elif processor >= 48 and processor < 72: 
            return np.ceil(task_weight / 184).astype(int)
        elif processor >= 72 and processor < 96: 
            return np.ceil(task_weight / 254).astype(int)
        elif processor >= 96 and processor < 120: 
            return np.ceil(task_weight / 706).astype(int)
        elif processor >= 120 and processor < 144: 
            return np.ceil(task_weight / 581).astype(int)    

def parse_weights(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File '{file_path}' not found!")
    
    with open(file_path, 'r') as file:
        dag_content = file.read()
    
    weight_pattern = r'(\d+)\s*\[weight=(\d+)\];'
    matches = re.findall(weight_pattern, dag_content)

    # Build dict: {node_id: weight}
    current_weights = {int(node_id): int(weight) for node_id, weight in matches}
    return current_weights

def read_mapping(mapping_path):
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(f"File '{mapping_path}' not found!")
    
    # first line is just one integer (number of processors)
    with open(mapping_path, 'r') as file:
        lines = file.readlines()
    num_processors = int(lines[0].strip())
    processor = 0
    mapping = {}
    for line in lines[1:]:
        mapping[processor] = []
        if line.strip() and not line.startswith("#"):
            parts = line.split()
            # assign processor all tasks in this line
            for part in parts:
                task = int(part)
                mapping[processor].append(task)
        processor += 1
    return num_processors,mapping

def adjust_weights(dag_file, processor_of_tasks, weights, numProcessors, output_file):
    variant = None
    if numProcessors == 72:
        variant = "small"
    elif numProcessors == 144:
        variant = "large"
    # replace weights in dag_file based on processor_of_tasks and get_running_time
    if not os.path.exists(dag_file):
        raise FileNotFoundError(f"File '{dag_file}' not found!")   
    with open(dag_file, 'r') as file:
        dag_content = file.read()

    # Replace weights in dag_content based on processor_of_tasks
    for task, processor in processor_of_tasks.items():
        # Get the current weight of the task
        current_weight = weights[task]
        # Get the running time for the task on the assigned processor
        running_time = get_running_time(current_weight, processor, variant)
        # Replace the weight in the DAG content
        # Regex: match the full integer node ID, not part of another number
        pattern = rf'(?<!\d){task}(?!\d)\s*\[weight=\d+\];'
        replacement = rf'{task} [weight={running_time}];'

        dag_content = re.sub(pattern, replacement, dag_content)

    # Write the adjusted DAG content to adjusted_dag_file
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the output path
    output_filename = output_file
    output_path = os.path.join(script_dir, output_filename)

    with open(output_path, 'w') as file:
        file.write(dag_content)



def main():
    parser = argparse.ArgumentParser(description="Adjust DAG weights based on processor-task mapping.")
    parser.add_argument("dag_file_path", type=str, help="Path to the input DAG file.")
    parser.add_argument("mapping_file_path", type=str, help="Path to the processor-task mapping file.")
    parser.add_argument("output_file", type=str, help="Path to the output adjusted DAG file.")

    args = parser.parse_args()

    dag_file_path = args.dag_file_path
    mapping_file_path = args.mapping_file_path
    output_file = args.output_file

    numProcessors, mapping = read_mapping(mapping_file_path)
    weights = parse_weights(dag_file_path)

    processor_of_tasks = {}
    for p in mapping:
        for t in mapping[p]:
            processor_of_tasks[t] = p

    adjust_weights(dag_file_path, processor_of_tasks, weights, numProcessors, output_file)

if __name__ == "__main__":
    main()

import os

low_balanced = [11, 11]
low_unbalanced = [11, 6]

medium_balanced = [22, 22]
medium_unbalanced = [22, 11]

high_balanced = [32, 32]
high_unbalanced = [32, 16]


traffic_conditions = [low_balanced, low_unbalanced, medium_balanced, medium_unbalanced, high_balanced, high_unbalanced]
# reward_types = ["stops", "speed", "wait"]
reward_types = ["stops", "wait"]
# reward_types = ['both']

configs = ['../scenarios/hangzhou/1.config',
           '../scenarios/ny16/1.config']
for config in configs:
    for reward in reward_types:
        # os.system("python runner.py --sim_config '../scenarios/loop_intersection/rings.config' --num_sim_steps 3600 --eps_start 1 --lr 0.0005 --mode train --agents_type learning --num_episodes 150 --replay True --mfd False --reward_type " + reward + " --n_vehs " + str(traffic[0]) + " " + str(traffic[1]))

# 'python runner.py --sim_config ../scenarios/2x2/1.config --num_sim_steps 3600 --eps_start 1 --lr 0.0005 --mode train --agents_type learning --num_episodes 100 --replay True --mfd False --reward_type stops'

        os.system(f'sbatch -n 8 --time=8:00:00 --wrap "python runner.py --sim_config {config} --num_sim_steps 3600 --eps_start 1 --lr 0.0005 --mode train --agents_type learning --num_episodes 200 --replay False --mfd False --reward_type {reward}"')
        

import numpy as np

ecg = np.load(r'D:\Project_3\python\ecg_normal.npy')
max_val = np.max(np.abs(ecg))
ecg_norm = ecg / max_val
ecg_q15 = np.round(np.clip(ecg_norm, -1.0, 0.99997) * 32768).astype(np.int16)
u16 = ecg_q15[:4096].view(np.uint16)

with open(r'D:\Project_3\vectors\ecg_normal_4096_hex.txt', 'w') as f:
    for v in u16:
        f.write(f'{v:04x}\n')

print("Done", len(u16), "samples")

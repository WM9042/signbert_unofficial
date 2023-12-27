import os
import gc
import glob
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import lightning.pytorch as pl
from psutil import Process
from torch.utils.data import DataLoader

from signbert.data_modules.PretrainMaskKeypointDataset import PretrainMaskKeypointDataset, mask_keypoint_dataset_collate_fn
from signbert.utils import read_json

from IPython import embed


class How2SignDataModule(pl.LightningDataModule):

    DPATH = '/home/tmpvideos/SLR/How2Sign/How2Sign'
    SKELETON_DPATH = os.path.join(DPATH, 'sentence_level')
    TRAIN_SKELETON_DPATH = os.path.join(SKELETON_DPATH, 'train', 'rgb_front', 'features', 'openpose_output', 'json')
    VAL_SKELETON_DPATH = os.path.join(SKELETON_DPATH, 'val', 'rgb_front', 'features', 'openpose_output', 'json')
    TEST_SKELETON_DPATH = os.path.join(SKELETON_DPATH, 'test', 'rgb_front', 'features', 'openpose_output', 'json')
    PREPROCESS_DPATH = os.path.join(DPATH, 'preprocess')
    MEANS_FPATH = os.path.join(PREPROCESS_DPATH, 'means.npy')
    STDS_FPATH = os.path.join(PREPROCESS_DPATH, 'stds.npy')
    TRAIN_FPATH = os.path.join(PREPROCESS_DPATH, 'train.npy')
    VAL_FPATH = os.path.join(PREPROCESS_DPATH, 'val.npy')
    TEST_FPATH = os.path.join(PREPROCESS_DPATH, 'test.npy')
    TRAIN_NORM_FPATH = os.path.join(PREPROCESS_DPATH, 'train_norm.npy')
    VAL_NORM_FPATH = os.path.join(PREPROCESS_DPATH, 'val_norm.npy')
    TEST_NORM_FPATH = os.path.join(PREPROCESS_DPATH, 'test_norm.npy')
    TRAIN_IDXS_FPATH = os.path.join(PREPROCESS_DPATH, 'train_idxs.npy')
    VAL_IDXS_FPATH = os.path.join(PREPROCESS_DPATH, 'val_idxs.npy')
    TEST_IDXS_FPATH = os.path.join(PREPROCESS_DPATH, 'test_idxs.npy')
    SEQ_PAD_VALUE = 0.0

    def __init__(self, batch_size, normalize=False, R=0.3, m=5, K=8, max_disturbance=0.25):
        super().__init__()
        self.batch_size = batch_size
        self.normalize = normalize
        self.R = R
        self.m = m
        self.K = K
        self.max_disturbance = max_disturbance

    def prepare_data(self):

        # Create preprocess path if it does not exist
        if not os.path.exists(How2SignDataModule.PREPROCESS_DPATH):
            os.makedirs(How2SignDataModule.PREPROCESS_DPATH)

        # Compute means and stds
        if not os.path.exists(How2SignDataModule.MEANS_FPATH) or \
            not os.path.exists(How2SignDataModule.STDS_FPATH):
            train = self._read_openpose_split(How2SignDataModule.TRAIN_SKELETON_DPATH)
            self._generate_means_stds(train)
        
        if not os.path.exists(How2SignDataModule.TRAIN_FPATH) or \
            not os.path.exists(How2SignDataModule.VAL_FPATH) or \
            not os.path.exists(How2SignDataModule.TEST_FPATH) or \
            not os.path.exists(How2SignDataModule.TRAIN_NORM_FPATH) or \
            not os.path.exists(How2SignDataModule.VAL_NORM_FPATH) or \
            not os.path.exists(How2SignDataModule.TEST_NORM_FPATH) or \
            not os.path.exists(How2SignDataModule.TRAIN_IDXS_FPATH) or \
            not os.path.exists(How2SignDataModule.VAL_IDXS_FPATH) or \
            not os.path.exists(How2SignDataModule.TEST_IDXS_FPATH):
            # train = self._read_openpose_split(How2SignDataModule.TRAIN_SKELETON_DPATH)
            # self._generate_preprocess_npy_arrays(
            #     range(len(train)), 
            #     train, 
            #     How2SignDataModule.TRAIN_FPATH, 
            #     How2SignDataModule.TRAIN_NORM_FPATH,
            #     How2SignDataModule.TRAIN_IDXS_FPATH,
            # )
            # del train
            # gc.collect()
            # val = self._read_openpose_split(How2SignDataModule.VAL_SKELETON_DPATH)
            # self._generate_preprocess_npy_arrays(
            #     range(len(val)), 
            #     val, 
            #     How2SignDataModule.VAL_FPATH, 
            #     How2SignDataModule.VAL_NORM_FPATH,
            #     How2SignDataModule.VAL_IDXS_FPATH,
            # )
            # del val
            # gc.collect()
            test = self._read_openpose_split(How2SignDataModule.TEST_SKELETON_DPATH)
            self._generate_preprocess_npy_arrays(
                range(len(test)), 
                test, 
                How2SignDataModule.TEST_FPATH, 
                How2SignDataModule.TEST_NORM_FPATH,
                How2SignDataModule.TEST_IDXS_FPATH,
            )
            del test
            gc.collect()
            
    def setup(self, stage=None):
        if stage == 'fit' or stage is None:
            X_train_fpath = How2SignDataModule.TRAIN_NORM_FPATH if self.normalize else How2SignDataModule.TRAIN_FPATH
            X_val_fpath = How2SignDataModule.VAL_NORM_FPATH if self.normalize else How2SignDataModule.VAL_FPATH
            X_test_fpath = How2SignDataModule.TEST_NORM_FPATH if self.normalize else How2SignDataModule.TEST_FPATH

            self.setup_train = PretrainMaskKeypointDataset(
                How2SignDataModule.TRAIN_IDXS_FPATH, 
                X_train_fpath, 
                self.R, 
                self.m, 
                self.K, 
                self.max_disturbance
            )
            self.setup_val = PretrainMaskKeypointDataset(
                How2SignDataModule.VAL_IDXS_FPATH,
                X_val_fpath, 
                self.R, 
                self.m, 
                self.K, 
                self.max_disturbance
            )

    def train_dataloader(self):
        return DataLoader(self.setup_train, batch_size=self.batch_size, collate_fn=mask_keypoint_dataset_collate_fn, drop_last=True)

    def val_dataloader(self):
        return DataLoader(self.setup_val, batch_size=self.batch_size, collate_fn=mask_keypoint_dataset_collate_fn)

    def _read_openpose_split(self, split_fpath):
        skeleton_fpaths = glob.glob(os.path.join(split_fpath, '*')) 
        executor = ProcessPoolExecutor(max_workers=os.cpu_count())
        futures = []
        for f in skeleton_fpaths:
            future = executor.submit(self._read_openpose_json_out, f)
            futures.append(future)
        results = [f.result() for f in futures] 
        executor.shutdown()

        return results


    def _read_openpose_json_out(self, fpath):
        json_fpaths = sorted(glob.glob(os.path.join(fpath, '*.json')))
        data = []
        for f in json_fpaths:
            raw_data = read_json(f)['people'][0]
            face_kps = np.array(raw_data['face_keypoints_2d']).reshape(-1, 3)
            pose_kps = np.array(raw_data['pose_keypoints_2d']).reshape(-1, 3)
            lhand_kps = np.array(raw_data['hand_left_keypoints_2d']).reshape(-1, 3)
            rhand_kps = np.array(raw_data['hand_right_keypoints_2d']).reshape(-1, 3)
            kps = np.concatenate((face_kps, pose_kps, lhand_kps, rhand_kps))
            data.append(kps)
        data = np.stack(data)

        return data

    def _generate_means_stds(self, train_data):
        seq_concats = np.concatenate([s[..., :2] for s in train_data], axis=0)
        means = seq_concats.mean((0, 1))
        stds = seq_concats.std((0, 1))
        np.save(How2SignDataModule.MEANS_FPATH, means)
        np.save(How2SignDataModule.STDS_FPATH, stds)

    def _generate_preprocess_npy_arrays(
            self, 
            split_idxs, 
            skeleton_fpaths, 
            out_fpath,
            norm_out_fpath,
            idxs_out_fpath,
            max_seq_len=500
        ):
        seqs = []
        for seq in skeleton_fpaths:
            if seq.shape[0] > max_seq_len:
                split_indices = list(range(max_seq_len, seq.shape[0], max_seq_len))
                seq = np.array_split(seq, split_indices, axis=0)
                for s in seq:
                    seqs.append(s)
            else:
                seqs.append(seq)
        seqs_idxs = range(len(seqs)) 
        seqs_norm = self._normalize_seqs(seqs)
        seqs = self._pad_seqs_by_max_len(seqs)
        seqs_norm = self._pad_seqs_by_max_len(seqs_norm)
        seqs = seqs.astype(np.float32)
        seqs_norm = seqs_norm.astype(np.float32)
        seqs_idxs = np.array(seqs_idxs, dtype=np.int32)
        np.save(out_fpath, seqs)
        np.save(norm_out_fpath, seqs_norm)
        np.save(idxs_out_fpath, seqs_idxs)
        del seqs
        del seqs_norm
        del seqs_idxs
        gc.collect()
    
    def _normalize_seqs(self, seqs):
        means = np.load(How2SignDataModule.MEANS_FPATH)
        stds = np.load(How2SignDataModule.STDS_FPATH)
        # Append identity to not affect the score
        means = np.concatenate((means, [0]), -1)
        stds = np.concatenate((stds, [1]), -1)
        seqs_norm = [(s - means) / stds for s in seqs]

        return seqs_norm
    
    def _pad_seqs_by_max_len(self, seqs):
        seqs_len = [len(t) for t in seqs]
        max_seq_len = max(seqs_len)
        lmdb_gen_pad_seq = lambda s_len: ((0,max_seq_len-s_len), (0,0), (0,0))
        seqs = np.stack([
            np.pad(
                array=t, 
                pad_width=lmdb_gen_pad_seq(seqs_len[i]),
                mode='constant',
                constant_values=How2SignDataModule.SEQ_PAD_VALUE
            ) 
            for i, t in enumerate(seqs)
        ])

        return seqs


if __name__ == '__main__':

    d = How2SignDataModule(
        batch_size=32,
        normalize=True,
    )
    d.prepare_data()
    d.setup()
    dl = d.train_dataloader()
    sample = next(iter(dl))
    embed()
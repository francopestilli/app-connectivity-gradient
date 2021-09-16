import argparse
import os.path

import nibabel as nb
from nilearn import datasets
from nibabel.gifti.gifti import GiftiImage, GiftiDataArray

import numpy as np
from brainspace.gradient import GradientMaps
from nilearn.connectome import ConnectivityMeasure


def is_valid_surface_data(parser, arg):
    if not os.path.exists(arg):
        parser.error(f"The folder {arg} does not exist!")
    lh = os.path.join(arg, 'left.gii')
    if not os.path.exists(lh):
        parser.error(f"The file {lh} does not exist!")
    rh = os.path.join(arg, 'right.gii')
    if not os.path.exists(rh):
        parser.error(f"The file {rh} does not exist!")
    return (lh, rh)

parser = argparse.ArgumentParser(description='Connectivity Gradients')
parser.add_argument('approach', choices=['diffusion-maps', 'laplacian-eigenmaps', 'pca-maps'])
parser.add_argument('kernel', choices=['pearson', 'spearman', 'normalized-angle', 'cosine', 'gaussian'])
parser.add_argument('input', type=lambda x: is_valid_surface_data(parser, x))
parser.add_argument('--n_components', default=3, type=int)
parser.add_argument('--random_state', default=0, type=int)

args = parser.parse_args()

approach = {
    'diffusion-maps': 'dm',
    'laplacian-eigenmaps': 'le',
    'pca-maps': 'pca',
}[args.approach]
kernel = args.kernel.replace('-', '_')


lh = nb.load(args.input[0]).agg_data('time series')
rh = nb.load(args.input[1]).agg_data('time series')
lh_shape = lh.shape
rh_shape = rh.shape

data = np.concatenate((lh, rh))
data_shape = data.shape

del lh, rh

atlas = datasets.fetch_atlas_surf_destrieux()
regions = atlas['labels'].copy()
masked_regions = [b'Medial_wall', b'Unknown']
masked_labels = [regions.index(r) for r in masked_regions]
regions = [r for r in regions if r not in masked_regions]
labeling = np.concatenate([atlas['map_left'], atlas['map_right']])
mask = ~np.isin(labeling, masked_labels)
data = data[mask]

corr = ConnectivityMeasure(kind='correlation').fit_transform([data.T])[0]
gm = GradientMaps(
    n_components=args.n_components,
    kernel=kernel,
    approach=approach,
    random_state=args.random_state
)
gm.fit(corr)

del corr

gradients = np.zeros((data_shape[0], gm.gradients_.shape[1]))
gradients[np.where(mask)[0]] = gm.gradients_

for g in range(args.n_components):
    new_img = GiftiImage()
    new_img.add_gifti_data_array(
        GiftiDataArray(
            gradients[:lh_shape[0], g],
            'NIFTI_INTENT_TIME_SERIES',
            'NIFTI_TYPE_FLOAT32'
        )
    )
    nb.save(new_img, f'lh.gradient{g + 1}.func.gii')

    new_img = GiftiImage()
    new_img.add_gifti_data_array(
        GiftiDataArray(
            gradients[lh_shape[0]:, g],
            'NIFTI_INTENT_TIME_SERIES',
            'NIFTI_TYPE_FLOAT32'
        )
    )
    nb.save(new_img, f'rh.gradient{g + 1}.func.gii')

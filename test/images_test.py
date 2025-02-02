import matplotlib.pyplot as plt
import pytest
import torch
from astropy.io import fits

from mpol import images, utils
from mpol.constants import *


def test_odd_npix():
    expected_error_message = "Image must have an even number of pixels."

    with pytest.raises(ValueError, match=expected_error_message):
        images.BaseCube.from_image_properties(npix=853, nchan=30, cell_size=0.015)

    with pytest.raises(ValueError, match=expected_error_message):
        images.ImageCube.from_image_properties(npix=853, nchan=30, cell_size=0.015)


def test_negative_cell_size():
    expected_error_message = "cell_size must be a positive real number."

    with pytest.raises(ValueError, match=expected_error_message):
        images.BaseCube.from_image_properties(npix=800, nchan=30, cell_size=-0.015)

    with pytest.raises(ValueError, match=expected_error_message):
        images.ImageCube.from_image_properties(npix=800, nchan=30, cell_size=-0.015)


def test_single_chan():
    im = images.ImageCube.from_image_properties(cell_size=0.015, npix=800)
    assert im.nchan == 1


def test_basecube_grad():
    bcube = images.BaseCube.from_image_properties(npix=800, cell_size=0.015)
    loss = torch.sum(bcube())
    loss.backward()


def test_imagecube_grad(coords):
    bcube = images.BaseCube(coords=coords)
    # try passing through ImageLayer
    imagecube = images.ImageCube(coords=coords, passthrough=True)

    # send things through this layer
    loss = torch.sum(imagecube(bcube()))

    loss.backward()


# test for proper fits scale
def test_imagecube_tofits(coords, tmp_path):
    # creating base cube
    bcube = images.BaseCube(coords=coords)

    # try passing through ImageLayer
    imagecube = images.ImageCube(coords=coords, passthrough=True)

    # sending the basecube through the imagecube
    imagecube(bcube())

    # creating output fits file with name 'test_cube_fits_file39.fits'
    # file will be deleted after testing
    imagecube.to_FITS(fname=tmp_path / "test_cube_fits_file39.fits", overwrite=True)

    # inputting the header from the previously created fits file
    fits_header = fits.open(tmp_path / "test_cube_fits_file39.fits")[0].header
    assert (fits_header["CDELT1"] and fits_header["CDELT2"]) == pytest.approx(
        coords.cell_size / 3600
    )


def test_basecube_imagecube(coords, tmp_path):
    # create a mock cube that includes negative values
    nchan = 1
    mean = torch.full(
        (nchan, coords.npix, coords.npix), fill_value=-0.5, dtype=torch.double
    )
    std = torch.full(
        (nchan, coords.npix, coords.npix), fill_value=0.5, dtype=torch.double
    )

    # tensor
    base_cube = torch.normal(mean=mean, std=std)

    # layer
    basecube = images.BaseCube(coords=coords, nchan=nchan, base_cube=base_cube)

    # the default softplus function should map everything to positive values
    output = basecube()

    fig, ax = plt.subplots(ncols=2, nrows=1)

    im = ax[0].imshow(
        np.squeeze(base_cube.detach().numpy()), origin="lower", interpolation="none"
    )
    plt.colorbar(im, ax=ax[0])
    ax[0].set_title("input")

    im = ax[1].imshow(
        np.squeeze(output.detach().numpy()), origin="lower", interpolation="none"
    )
    plt.colorbar(im, ax=ax[1])
    ax[1].set_title("mapped")

    fig.savefig(tmp_path / "basecube_mapped.png", dpi=300)

    # try passing through ImageLayer
    imagecube = images.ImageCube(coords=coords, nchan=nchan, passthrough=True)

    # send things through this layer
    imagecube(basecube())

    fig, ax = plt.subplots(ncols=1)
    im = ax.imshow(
        np.squeeze(imagecube.sky_cube.detach().numpy()),
        extent=imagecube.coords.img_ext,
        origin="lower",
        interpolation="none",
    )
    fig.savefig(tmp_path / "imagecube.png", dpi=300)

    plt.close("all")


def test_base_cube_conv_cube(coords, tmp_path):
    # test whether the HannConvCube functions appropriately

    # create a mock cube that includes negative values
    nchan = 1
    mean = torch.full(
        (nchan, coords.npix, coords.npix), fill_value=-0.5, dtype=torch.double
    )
    std = torch.full(
        (nchan, coords.npix, coords.npix), fill_value=0.5, dtype=torch.double
    )

    # The HannConvCube expects to function on a pre-packed ImageCube,
    # so in order to get the plots looking correct on this test image,
    # we need to faff around with packing

    # tensor
    test_cube = torch.normal(mean=mean, std=std)
    test_cube_packed = utils.sky_cube_to_packed_cube(test_cube)

    # layer
    conv_layer = images.HannConvCube(nchan=nchan)

    conv_output_packed = conv_layer(test_cube_packed)
    conv_output = utils.packed_cube_to_sky_cube(conv_output_packed)

    fig, ax = plt.subplots(ncols=2, nrows=1)

    im = ax[0].imshow(
        np.squeeze(test_cube.detach().numpy()), origin="lower", interpolation="none"
    )
    plt.colorbar(im, ax=ax[0])
    ax[0].set_title("input")

    im = ax[1].imshow(
        np.squeeze(conv_output.detach().numpy()), origin="lower", interpolation="none"
    )
    plt.colorbar(im, ax=ax[1])
    ax[1].set_title("convolved")

    fig.savefig(tmp_path / "convcube.png", dpi=300)

    plt.close("all")


def test_multi_chan_conv(coords, tmp_path):
    # create a mock channel cube that includes negative values
    # and make sure that the HannConvCube works across channels

    nchan = 10
    mean = torch.full(
        (nchan, coords.npix, coords.npix), fill_value=-0.5, dtype=torch.double
    )
    std = torch.full(
        (nchan, coords.npix, coords.npix), fill_value=0.5, dtype=torch.double
    )

    # tensor
    test_cube = torch.normal(mean=mean, std=std)

    # layer
    conv_layer = images.HannConvCube(nchan=nchan)

    conv_layer(test_cube)

def test_image_flux(coords):
    nchan = 20
    im = images.ImageCube(coords=coords, nchan=nchan)    
    assert im.flux.size()[0] == nchan

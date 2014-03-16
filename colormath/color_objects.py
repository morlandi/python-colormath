"""
This module contains classes to represent various color spaces.
"""

import logging

import numpy as np

from colormath import color_conversions
from colormath import color_constants
from colormath import density
from colormath import color_diff, color_diff_matrix
from colormath.color_exceptions import InvalidConversion, InvalidObserver, \
    MissingValue, InvalidValue, InvalidDeltaEMode, InvalidIlluminant, \
    InvalidArgument

logger = logging.getLogger(__name__)


class ColorBase(object):
    """
    A base class holding some common methods and values.
    """

    # This is a table of conversions to/from this color space in the
    # sub-classed color class.
    CONVERSIONS = {}
    # Attribute names containing color data on the sub-class. For example,
    # the RGBColor would be ['rgb_r', 'rgb_g', 'rgb_b']
    VALUES = []
    OTHER_VALUES = ['illuminant', 'observer']

    # noinspection PyUnusedLocal
    def __init__(self, *args, **kwargs):
        # This is the most common illuminant, default to it.
        self.illuminant = 'd50'
        # This is the most commonly used observer angle.
        self.observer = '2'

    def _transfer_kwargs(self, *args, **kwargs):
        """
        Transfers any keyword arguments to the appropriate coordinate fields
        if they match one of the keys in the class's VALUES dict.

        Also transfers *args to the corresponding tristimulus values.
        """

        # Used for tracking which member of the VALUES list we're on.
        counter = 0
        # This is the max number of args used for VALUES.
        max_args = len(self.VALUES) - 1
        for arg in args:
            if counter <= max_args:
                # Transfer the tri-stim value.
                setattr(self, self.VALUES[counter], arg)
                counter += 1

        # Transfer matching keywords.
        attrib_list = self.VALUES + self.OTHER_VALUES
        for key, val in list(kwargs.items()):
            if key in attrib_list:
                # This is useful for stuff like illuminants. All of our
                # constants dictionaries are lowercase.
                if isinstance(val, str):
                    val = val.lower()
                # Transfer the value to the color object.
                setattr(self, key, val)

    def __prep_strings(self):
        """
        Makes sure all string variables are lowercase beforehand.
        """

        self.illuminant = self.illuminant.lower()
        self.observer = str(self.observer)

    def convert_to(self, cs_to, *args, **kwargs):
        """
        Converts the color to the designated colorspace.
        """

        try:
            # Look up the conversion path for the specified color space.
            conversions = self.CONVERSIONS[cs_to.lower()]
        except KeyError:
            raise InvalidConversion(self.__class__.__name__, cs_to)

        # Make sure any string variables are lowercase.
        self.__prep_strings()
        # Make sure the object has all of its required values before even
        # attempting a conversion.
        self.has_required_values()

        logger.debug('Converting %s to %s', self, cs_to)
        logger.debug(' @ Conversion path: %s', conversions)

        cobj = self
        # Iterate through the list of functions for the conversion path, storing
        # the results in a dictionary via update(). This way the user has access
        # to all of the variables involved in the conversion.
        for func in conversions:
            # Execute the function in this conversion step and store the resulting
            # Color object.
            logger.debug(' * Conversion: %s passed to %s()',
                         cobj.__class__.__name__, func)
            logger.debug(' |->  in %s', cobj)

            if func:
                # This can be None if you try to convert a color to the color
                # space that is already in. IE: XYZ->XYZ.
                cobj = func(cobj, *args, **kwargs)

            logger.debug(' |-< out %s', cobj)
        return cobj

    def get_value_tuple(self):
        """
        Returns a tuple of the color's values (in order). For example,
        an LabColor object will return (lab_l, lab_a, lab_b), where each
        member of the tuple is the float value for said variable.
        """

        retval = tuple()
        for val in self.VALUES:
            retval += (getattr(self, val, None),)
        return retval

    def __str__(self):
        """
        String representation of the color.
        """

        retval = self.__class__.__name__ + ' ('
        for val in self.VALUES:
            value = getattr(self, val, None)
            if value is not None:
                retval += '%s:%.4f ' % (val, getattr(self, val))
        return retval.strip() + ')'

    def __repr__(self):
        """
        String representation of the object.
        """

        retval = self.__class__.__name__ + '('
        attributes = [(attr, getattr(self, attr)) for attr in self.VALUES + self.OTHER_VALUES]
        values = [x + "=" + repr(y) for x, y in attributes]
        retval += ','.join(values)
        return retval + ')'

    def has_required_values(self):
        """
        Checks various fields for None or invalid values.
        """

        if self.observer not in ['2', '10']:
            raise InvalidObserver(self)

        for val in self.VALUES:
            value = getattr(self, val, None)
            if value is None:
                # A required value is missing.
                raise MissingValue(self, val)

            try:
                # If this fails, it's not a usable number.
                float(value)
            except ValueError:
                raise InvalidValue(self, val, value)
        return True

    def get_illuminant_xyz(self, observer=None, illuminant=None):
        """
        :param str observer: Get the XYZ values for another observer angle. Must
            be either '2' or '10'.
        :param str illuminant: Get the XYZ values for another illuminant.
        :returns: the color's illuminant's XYZ values.
        """

        try:
            if observer is None:
                observer = self.observer

            illums_observer = color_constants.ILLUMINANTS[observer]
        except KeyError:
            raise InvalidObserver(self)

        try:
            if illuminant is None:
                illuminant = self.illuminant

            illum_xyz = illums_observer[illuminant]
        except AttributeError:
            raise InvalidIlluminant(self)
        except KeyError:
            raise InvalidIlluminant(self)

        return {'X': illum_xyz[0], 'Y': illum_xyz[1], 'Z': illum_xyz[2]}

    def delta_e(self, other_color, mode='cie2000', *args, **kwargs):
        """
        Compares this color to another via Delta E.

        Valid modes:
         cie2000
         cie1976
        """

        if not isinstance(other_color, ColorBase):
            raise InvalidArgument('delta_e_cie2000', 'other_color', other_color)

        # Convert the colors to Lab if they are not already.
        lab1 = self.convert_to('lab', *args, **kwargs)
        lab2 = other_color.convert_to('lab', *args, **kwargs)

        mode = mode.lower()
        if mode == 'cie2000':
            return color_diff.delta_e_cie2000(lab1, lab2)
        elif mode == 'cie1994':
            return color_diff.delta_e_cie1994(lab1, lab2, **kwargs)
        elif mode == 'cie1976':
            return color_diff.delta_e_cie1976(lab1, lab2)
        elif mode == 'cmc':
            return color_diff.delta_e_cmc(lab1, lab2, **kwargs)
        else:
            raise InvalidDeltaEMode(mode)


class SpectralColor(ColorBase):
    """
    Represents a color that may have operations done to it. You need not use
    this object with the library as long as you use all of the instance
    variables here.
    """

    CONVERSIONS = {
        "spectral": [None],
        "xyz": [color_conversions.Spectral_to_XYZ],
        "xyy": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_Lab],
        "lch": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_Lab,
                color_conversions.Lab_to_LCHab],
        "luv": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_Luv],
        "rgb": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_RGB],
        "hsl": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_HSV],
        "cmy": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.Spectral_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_CMY, color_conversions.CMY_to_CMYK],
    }
    VALUES = ['spec_340nm', 'spec_350nm', 'spec_360nm', 'spec_370nm',
              'spec_380nm', 'spec_390nm', 'spec_400nm', 'spec_410nm',
              'spec_420nm', 'spec_430nm', 'spec_440nm', 'spec_450nm',
              'spec_460nm', 'spec_470nm', 'spec_480nm', 'spec_490nm',
              'spec_500nm', 'spec_510nm', 'spec_520nm', 'spec_530nm',
              'spec_540nm', 'spec_550nm', 'spec_560nm', 'spec_570nm',
              'spec_580nm', 'spec_590nm', 'spec_600nm', 'spec_610nm',
              'spec_620nm', 'spec_630nm', 'spec_640nm', 'spec_650nm',
              'spec_660nm', 'spec_670nm', 'spec_680nm', 'spec_690nm',
              'spec_700nm', 'spec_710nm', 'spec_720nm', 'spec_730nm',
              'spec_740nm', 'spec_750nm', 'spec_760nm', 'spec_770nm',
              'spec_780nm', 'spec_790nm', 'spec_800nm', 'spec_810nm',
              'spec_820nm', 'spec_830nm']

    def __init__(self, *args, **kwargs):
        super(SpectralColor, self).__init__(*args, **kwargs)
        # Spectral fields
        self.spec_340nm = 0.0
        self.spec_350nm = 0.0
        self.spec_360nm = 0.0
        self.spec_370nm = 0.0
        # begin Blue wavelengths
        self.spec_380nm = 0.0
        self.spec_390nm = 0.0
        self.spec_400nm = 0.0
        self.spec_410nm = 0.0
        self.spec_420nm = 0.0
        self.spec_430nm = 0.0
        self.spec_440nm = 0.0
        self.spec_450nm = 0.0
        self.spec_460nm = 0.0
        self.spec_470nm = 0.0
        self.spec_480nm = 0.0
        # end Blue wavelengths
        self.spec_490nm = 0.0
        # start Green wavelengths
        self.spec_500nm = 0.0
        self.spec_510nm = 0.0
        self.spec_520nm = 0.0
        self.spec_530nm = 0.0
        self.spec_540nm = 0.0
        self.spec_550nm = 0.0
        self.spec_560nm = 0.0
        self.spec_570nm = 0.0
        self.spec_580nm = 0.0
        self.spec_590nm = 0.0
        self.spec_600nm = 0.0
        # end Green wavelengths
        self.spec_610nm = 0.0
        # start Red wavelengths
        self.spec_620nm = 0.0
        self.spec_630nm = 0.0
        self.spec_640nm = 0.0
        self.spec_650nm = 0.0
        self.spec_660nm = 0.0
        self.spec_670nm = 0.0
        self.spec_680nm = 0.0
        self.spec_690nm = 0.0
        self.spec_700nm = 0.0
        self.spec_710nm = 0.0
        self.spec_720nm = 0.0
        # end Red wavelengths
        self.spec_730nm = 0.0
        self.spec_740nm = 0.0
        self.spec_750nm = 0.0
        self.spec_760nm = 0.0
        self.spec_770nm = 0.0
        self.spec_780nm = 0.0
        self.spec_790nm = 0.0
        self.spec_800nm = 0.0
        self.spec_810nm = 0.0
        self.spec_820nm = 0.0
        self.spec_830nm = 0.0
        self._transfer_kwargs(*args, **kwargs)

    def get_numpy_array(self):
        """
        Dump this color into NumPy array.
        """

        # This holds the obect's spectral data, and will be passed to
        # numpy.array() to create a numpy array (matrix) for the matrix math
        # that will be done during the conversion to XYZ.
        values = []

        # Use the required value list to build this dynamically. Default to
        # 0.0, since that ultimately won't affect the outcome due to the math
        # involved.
        for val in self.VALUES:
            values.append(getattr(self, val, 0.0))

        # Create and the actual numpy array/matrix from the spectral list.
        color_array = np.array([values])
        return color_array

    def calc_density(self, density_standard=None):
        """
        Calculates the density of the SpectralColor. By default, Status T
        density is used, and the correct density distribution (Red, Green,
        or Blue) is chosen by comparing the Red, Green, and Blue components of
        the spectral sample (the values being red in via "filters").
        """

        if density_standard is not None:
            return density.ansi_density(self, density_standard)
        else:
            return density.auto_density(self)


class LabColor(ColorBase):
    """
    Represents an Lab color.
    """

    CONVERSIONS = {
        "lab": [None],
        "xyz": [color_conversions.Lab_to_XYZ],
        "xyy": [color_conversions.Lab_to_XYZ, color_conversions.XYZ_to_xyY],
      "lchab": [color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.Lab_to_XYZ, color_conversions.XYZ_to_Luv,
                color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.Lab_to_XYZ, color_conversions.XYZ_to_Luv],
        "rgb": [color_conversions.Lab_to_XYZ, color_conversions.XYZ_to_RGB],
        "hsl": [color_conversions.Lab_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.Lab_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_HSV],
        "cmy": [color_conversions.Lab_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.Lab_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_CMY, color_conversions.CMY_to_CMYK],
    }
    VALUES = ['lab_l', 'lab_a', 'lab_b']

    def __init__(self, *args, **kwargs):
        super(LabColor, self).__init__(*args, **kwargs)
        self.lab_l = None
        self.lab_a = None
        self.lab_b = None
        self._transfer_kwargs(*args, **kwargs)

    # noinspection PyUnusedLocal
    def delta_e_matrix(self, lab_color_matrix, mode='cie2000', *args, **kwargs):
        """
        Compares this object with all colors in lab_color_matrix via Delta E.
        The matrix must be of shape (n,3) and must be composed of floats.
        Returns a distance vector of shape (n,).

        Valid modes:
         cie2000
         cie1976
         cie1994
         cmc
        """

        lab_color_vector = np.array([self.lab_l, self.lab_a, self.lab_b])

        mode = mode.lower()

        if mode == 'cie2000':
            return color_diff_matrix.delta_e_cie2000(
                lab_color_vector, lab_color_matrix)
        elif mode == 'cie1994':
            return color_diff_matrix.delta_e_cie1994(
                lab_color_vector, lab_color_matrix, **kwargs)
        elif mode == 'cie1976':
            return color_diff_matrix.delta_e_cie1976(
                lab_color_vector, lab_color_matrix)
        elif mode == 'cmc':
            return color_diff_matrix.delta_e_cmc(
                lab_color_vector, lab_color_matrix, **kwargs)
        else:
            raise InvalidDeltaEMode(mode)


class LCHabColor(ColorBase):
    """
    Represents an LCHab color.
    """

    CONVERSIONS = {
      "lchab": [None],
        "xyz": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ],
        "xyy": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ,
                color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.LCHab_to_Lab],
      "lchuv": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ,
                color_conversions.XYZ_to_Luv, color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ,
                color_conversions.XYZ_to_Luv],
        "rgb": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ,
                color_conversions.XYZ_to_RGB],
        "hsl": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ,
                color_conversions.XYZ_to_RGB, color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ,
                color_conversions.XYZ_to_RGB, color_conversions.RGB_to_HSV],
        "cmy": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ,
                color_conversions.XYZ_to_RGB, color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.LCHab_to_Lab, color_conversions.Lab_to_XYZ,
                color_conversions.XYZ_to_RGB, color_conversions.RGB_to_CMY,
                color_conversions.CMY_to_CMYK],
    }
    VALUES = ['lch_l', 'lch_c', 'lch_h']

    def __init__(self, *args, **kwargs):
        super(LCHabColor, self).__init__(*args, **kwargs)
        self.lch_l = None
        self.lch_c = None
        self.lch_h = None
        self._transfer_kwargs(*args, **kwargs)


class LCHuvColor(ColorBase):
    """
    Represents an LCHuv color.
    """

    CONVERSIONS = {
      "lchuv": [None],
        "xyz": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ],
        "xyy": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ,
                color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ,
                color_conversions.XYZ_to_Lab],
        "luv": [color_conversions.LCHuv_to_Luv],
      "lchab": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ,
                color_conversions.XYZ_to_Lab, color_conversions.Lab_to_LCHab],
        "rgb": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ,
                color_conversions.XYZ_to_RGB],
        "hsl": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ,
                color_conversions.XYZ_to_RGB, color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ,
                color_conversions.XYZ_to_RGB, color_conversions.RGB_to_HSV],
        "cmy": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ,
                color_conversions.XYZ_to_RGB, color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.LCHuv_to_Luv, color_conversions.Luv_to_XYZ,
                color_conversions.XYZ_to_RGB, color_conversions.RGB_to_CMY,
                color_conversions.CMY_to_CMYK],
    }
    VALUES = ['lch_l', 'lch_c', 'lch_h']

    def __init__(self, *args, **kwargs):
        super(LCHuvColor, self).__init__(*args, **kwargs)
        self.lch_l = None
        self.lch_c = None
        self.lch_h = None
        self._transfer_kwargs(*args, **kwargs)


class LuvColor(ColorBase):
    """
    Represents an Luv color.
    """

    CONVERSIONS = {
        "luv": [None],
        "xyz": [color_conversions.Luv_to_XYZ],
        "xyy": [color_conversions.Luv_to_XYZ, color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.Luv_to_XYZ, color_conversions.XYZ_to_Lab],
      "lchab": [color_conversions.Luv_to_XYZ, color_conversions.XYZ_to_Lab,
                color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.Luv_to_LCHuv],
        "rgb": [color_conversions.Luv_to_XYZ, color_conversions.XYZ_to_RGB],
        "hsl": [color_conversions.Luv_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.Luv_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_HSV],
        "cmy": [color_conversions.Luv_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.Luv_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_CMY, color_conversions.CMY_to_CMYK],
    }
    VALUES = ['luv_l', 'luv_u', 'luv_v']

    def __init__(self, *args, **kwargs):
        super(LuvColor, self).__init__(*args, **kwargs)
        self.luv_l = None
        self.luv_u = None
        self.luv_v = None
        self._transfer_kwargs(*args, **kwargs)


class XYZColor(ColorBase):
    """
    Represents an XYZ color.
    """

    CONVERSIONS = {
        "xyz": [None],
        "xyy": [color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.XYZ_to_Lab],
      "lchab": [color_conversions.XYZ_to_Lab, color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.XYZ_to_Lab, color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.XYZ_to_Luv],
        "rgb": [color_conversions.XYZ_to_RGB],
        "hsl": [color_conversions.XYZ_to_RGB, color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.XYZ_to_RGB, color_conversions.RGB_to_HSV],
        "cmy": [color_conversions.XYZ_to_RGB, color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.XYZ_to_RGB, color_conversions.RGB_to_CMY,
                color_conversions.CMY_to_CMYK],
    }
    VALUES = ['xyz_x', 'xyz_y', 'xyz_z']

    def apply_adaptation(self, target_illuminant, adaptation='bradford'):
        """
        This applies an adaptation matrix to change the XYZ color's illuminant.
        You'll most likely only need this during RGB conversions.
        """

        # The illuminant of the original RGB object.
        source_illuminant = self.illuminant

        logger.debug("  \- Original illuminant: %s", self.illuminant)
        logger.debug("  \- Target illuminant: %s", target_illuminant)

        # If the XYZ values were taken with a different reference white than the
        # native reference white of the target RGB space, a transformation matrix
        # must be applied.
        if source_illuminant != target_illuminant:
            logger.debug("  \* Applying transformation from %s to %s ",
                         source_illuminant, target_illuminant)
            # Get the adjusted XYZ values, adapted for the target illuminant.
            self.xyz_x, self.xyz_y, self.xyz_z \
                = color_conversions.apply_XYZ_transformation(
                    self.xyz_x,
                    self.xyz_y,
                    self.xyz_z,
                    orig_illum=source_illuminant,
                    targ_illum=target_illuminant)
            self.illuminant = target_illuminant.lower()

    def __init__(self, *args, **kwargs):
        super(XYZColor, self).__init__(*args, **kwargs)
        self.xyz_x = None
        self.xyz_y = None
        self.xyz_z = None
        self._transfer_kwargs(*args, **kwargs)


# noinspection PyPep8Naming
class xyYColor(ColorBase):
    """
    Represents an xYy color.
    """

    CONVERSIONS = {
        "xyy": [None],
        "xyz": [color_conversions.xyY_to_XYZ],
        "lab": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_Lab],
      "lchab": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_Lab,
                color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_Luv,
                color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_Luv],
        "rgb": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_RGB],
        "hsl": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_HSV],
        "cmy": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.xyY_to_XYZ, color_conversions.XYZ_to_RGB,
                color_conversions.RGB_to_CMY, color_conversions.CMY_to_CMYK],
    }
    VALUES = ['xyy_x', 'xyy_y', 'xyy_Y']

    def __init__(self, *args, **kwargs):
        super(xyYColor, self).__init__(*args, **kwargs)
        self.xyy_x = None
        self.xyy_y = None
        self.xyy_Y = None
        self._transfer_kwargs(*args, **kwargs)


class RGBColor(ColorBase):
    """
    Represents an RGB color.
    """

    CONVERSIONS = {
        "rgb": [None],
        "hsl": [color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.RGB_to_HSV],
        "cmy": [color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.RGB_to_CMY, color_conversions.CMY_to_CMYK],
        "xyz": [color_conversions.RGB_to_XYZ],
        "xyy": [color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_Lab],
      "lchab": [color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_Lab,
                color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_Luv,
                color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_Luv],
    }
    VALUES = ['rgb_r', 'rgb_g', 'rgb_b']
    OTHER_VALUES = ['illuminant', 'observer', 'rgb_type']

    def __init__(self, *args, **kwargs):
        super(RGBColor, self).__init__(*args, **kwargs)
        self.rgb_r = None
        self.rgb_g = None
        self.rgb_b = None
        self.rgb_type = 'srgb'
        self._transfer_kwargs(*args, **kwargs)

    def __str__(self):
        parent_str = super(RGBColor, self).__str__()
        return '%s [%s]' % (parent_str, self.rgb_type)

    def get_rgb_hex(self):
        """
        Converts the RGB value to a hex value in the form of: #RRGGBB
        """

        self.has_required_values()
        return '#%02x%02x%02x' % (self.rgb_r, self.rgb_g, self.rgb_b)

    def set_from_rgb_hex(self, hex_str):
        """
        Converts an RGB hex string like #RRGGBB and assigns the values to
        this RGBColor object.
        """

        colorstring = hex_str.strip()
        if colorstring[0] == '#':
            colorstring = colorstring[1:]
        if len(colorstring) != 6:
            raise ValueError("input #%s is not in #RRGGBB format" % colorstring)
        r, g, b = colorstring[:2], colorstring[2:4], colorstring[4:]
        r, g, b = [int(n, 16) for n in (r, g, b)]
        self.rgb_r = r
        self.rgb_g = g
        self.rgb_b = b


class HSLColor(ColorBase):
    """
    Represents an HSL color.
    """

    CONVERSIONS = {
        "hsl": [None],
        "hsv": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_HSV],
        "rgb": [color_conversions.HSL_to_RGB],
        "cmy": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_CMY,
                color_conversions.CMY_to_CMYK],
        "xyz": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_XYZ],
        "xyy": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Lab],
      "lchab": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Lab, color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Luv, color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.HSL_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_RGB],
    }
    VALUES = ['hsl_h', 'hsl_s', 'hsl_l']
    OTHER_VALUES = ['illuminant', 'observer', 'rgb_type']

    def __init__(self, *args, **kwargs):
        super(HSLColor, self).__init__(*args, **kwargs)
        self.hsl_h = None
        self.hsl_s = None
        self.hsl_l = None
        self.rgb_type = 'srgb'
        self._transfer_kwargs(*args, **kwargs)


class HSVColor(ColorBase):
    """
    Represents an HSV color.
    """

    CONVERSIONS = {
        "hsv": [None],
        "hsl": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_HSL],
        "rgb": [color_conversions.HSV_to_RGB],
        "cmy": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_CMY],
       "cmyk": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_CMY,
                color_conversions.CMY_to_CMYK],
        "xyz": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_XYZ],
        "xyy": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Lab],
      "lchab": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Lab, color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Luv, color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.HSV_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_RGB],
    }
    VALUES = ['hsv_h', 'hsv_s', 'hsv_v']
    OTHER_VALUES = ['illuminant', 'observer', 'rgb_type']

    def __init__(self, *args, **kwargs):
        super(HSVColor, self).__init__(*args, **kwargs)
        self.hsv_h = None
        self.hsv_s = None
        self.hsv_v = None
        self.rgb_type = 'srgb'
        self._transfer_kwargs(*args, **kwargs)


class CMYColor(ColorBase):
    """
    Represents a CMY color.
    """

    CONVERSIONS = {
        "cmy": [None],
       "cmyk": [color_conversions.CMY_to_CMYK],
        "hsl": [color_conversions.CMY_to_RGB, color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.CMY_to_RGB, color_conversions.RGB_to_HSV],
        "rgb": [color_conversions.CMY_to_RGB],
        "xyz": [color_conversions.CMY_to_RGB, color_conversions.RGB_to_XYZ],
        "xyy": [color_conversions.CMY_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.CMY_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Lab],
      "lchab": [color_conversions.CMY_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Lab,
                color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.CMY_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_Luv, color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.CMY_to_RGB, color_conversions.RGB_to_XYZ,
                color_conversions.XYZ_to_RGB],
    }
    VALUES = ['cmy_c', 'cmy_m', 'cmy_y']

    def __init__(self, *args, **kwargs):
        super(CMYColor, self).__init__(*args, **kwargs)
        self.cmy_c = None
        self.cmy_m = None
        self.cmy_y = None
        self._transfer_kwargs(*args, **kwargs)


class CMYKColor(ColorBase):
    """
    Represents a CMYK color.
    """

    CONVERSIONS = {
       "cmyk": [None],
        "cmy": [color_conversions.CMYK_to_CMY],
        "hsl": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB,
                color_conversions.RGB_to_HSL],
        "hsv": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB,
                color_conversions.RGB_to_HSV],
        "rgb": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB],
        "xyz": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB,
                color_conversions.RGB_to_XYZ],
        "xyy": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB,
                color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_xyY],
        "lab": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB,
                color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_Lab],
      "lchab": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB,
                color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_Lab,
                color_conversions.Lab_to_LCHab],
      "lchuv": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB,
                color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_Luv,
                color_conversions.Luv_to_LCHuv],
        "luv": [color_conversions.CMYK_to_CMY, color_conversions.CMY_to_RGB,
                color_conversions.RGB_to_XYZ, color_conversions.XYZ_to_RGB],
    }
    VALUES = ['cmyk_c', 'cmyk_m', 'cmyk_y', 'cmyk_k']

    def __init__(self, *args, **kwargs):
        super(CMYKColor, self).__init__(*args, **kwargs)
        self.cmyk_c = None
        self.cmyk_m = None
        self.cmyk_y = None
        self.cmyk_k = None
        self._transfer_kwargs(*args, **kwargs)

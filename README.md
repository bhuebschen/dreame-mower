![Logo](https://raw.githubusercontent.com/Tasshack/dreame-vacuum/dev/docs/media/logo.png)

# Dreame/MOVA lawn mower integration for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/antondaubert/dreame-mower?style=flat-square)](https://github.com/antondaubert/dreame-mower/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://hacs.xyz/)

This is a custom integration for Home Assistant that allows you to control your Dreame lawn mower robot

## (current) Features

- Start/Pause/Stop mowing.
- Send back to home.
- Battery status.

### Please note: this is a modified version of Benedikt Hübschen's "Dreame Mower" to continue some active development, at least for some time.
### If you are interested in the original integration, please take a look at: https://github.com/bhuebschen/dreame-mower

## Installation

### HACS (Recommended)

1. Ensure that [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=antondaubert&repository=dreame-mower&category=integration)

-- or --

2. Add this repository as a custom repository in HACS:
   - Open HACS in Home Assistant.
   - Go to **Integrations**.
   - Click on the three dots in the top-right corner and select **Custom repositories**.
   - Add the following URL: `https://github.com/antondaubert/dreame-mower`.
   - Select **Integration** as the category.
3. Search for "Dreame Mower" in the HACS integrations list and install it.

### Manual Installation

1. Download the latest release from the [GitHub Releases page](https://github.com/antondaubert/dreame-mower/releases).
2. Extract the downloaded archive.
3. Copy the `custom_components/dreame-mower` folder to your Home Assistant `custom_components` directory.
   - Example: `/config/custom_components/dreame-mower`
4. Restart Home Assistant.

## Configuration

<a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=dreame_mower" target="_blank"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Open your Home Assistant instance and start setting up a new integration." /></a>

-- or --

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration**.
3. Search for "Dreame Mower" and select it.
4. Enter the credentials you used in your Dreamehome/MOVAhome App
5. Complete the setup process.

## Usage

Once the integration is configured, your Dreame/MOVA Mower(s) will appear as entities in Home Assistant.

## Troubleshooting

- Ensure your Dreame/MOVA account credentials are correct.
- Check the Home Assistant logs for any errors related to the integration.

## Support

If you encounter any issues or have feature requests, please open an issue on the [GitHub Issues page](https://github.com/antondaubert/dreame-mower/issues).

## Contributions

Contributions are welcome! Feel free to submit pull requests to improve this integration.

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/antondaubert/dreame-mower/blob/main/LICENSE) file for details.

# Thanks / Contributors

- [Aaroneisele55](https://github.com/Aaroneisele55)

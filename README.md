# Cuevana Scraper

A Python script for scraping movie details and video links from Cuevana3.is. This tool can extract movie information, find video sources, and generate Roku-compatible XML output.

## Prerequisites

- Python 3.x
- Chrome browser installed
- VLC media player installed
- Required Python packages:
  - selenium
  - retrying
  - webdriver_manager

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/cuevana-scraper.git
cd cuevana-scraper
```

2. Install required packages:
```bash
pip install selenium retrying webdriver_manager
```

## Usage

The script supports various command-line arguments for different functionalities:

### Basic Usage

```bash
python cuevana3.py "https://cuevana3.is/movie-url"
```

### Search for Movies

Search for movies in your movie_links.txt file:
```bash
python cuevana3.py -S "movie title"
```

### Play in VLC

Automatically play the found video link in VLC:
```bash
python cuevana3.py "https://cuevana3.is/movie-url" -VLC
```

### Generate Roku XML Output

Generate Roku-compatible XML for a single movie:
```bash
python cuevana3.py "https://cuevana3.is/movie-url" --rokuoutput
```

Process all movies from movie_links.txt:
```bash
python cuevana3.py --rokuall
```

Randomize the order when processing all movies:
```bash
python cuevana3.py --rokuall -r
```

### Save Working Links

Save working video links to a text file:
```bash
python cuevana3.py "https://cuevana3.is/movie-url" --rokufailed
```

### Source-Specific Options

You can specify which video source to use:

HD Sources:
```bash
python cuevana3.py "https://cuevana3.is/movie-url" --vidhide-hd
python cuevana3.py "https://cuevana3.is/movie-url" --filemoon-hd
python cuevana3.py "https://cuevana3.is/movie-url" --voesx-hd
```

CAM Sources:
```bash
python cuevana3.py "https://cuevana3.is/movie-url" --vidhide-cam
python cuevana3.py "https://cuevana3.is/movie-url" --filemoon-cam
python cuevana3.py "https://cuevana3.is/movie-url" --voesx-cam
```

## Output Files

The script generates several output files:

- `RokuChannelList.xml`: Contains the Roku-compatible XML output
- `MainHistory.txt`: Records successfully processed movies
- `scraper.log`: Detailed logging information
- Individual movie files (when using --rokufailed): Text files containing working video links

## Features

- Automatic movie details extraction
- Multiple video source support
- VLC integration for video playback testing
- Roku XML generation
- Comprehensive logging
- Source-specific video selection
- Batch processing of multiple movies
- Search functionality for movie_links.txt

## Notes

- The script requires Chrome browser to be installed
- VLC player is required for video playback testing
- Some websites may have anti-scraping measures in place
- The script includes various delays and retries to handle dynamic content loading

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
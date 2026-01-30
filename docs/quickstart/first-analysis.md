# Your First Analysis with SNID SAGE

Welcome to SNID SAGE! This guide will walk you through your first supernova spectrum analysis in just 5 minutes using the GUI interface.

## What You'll Learn

- How to load and analyze a spectrum
- Choosing the best cluster when multiple options exist
- Understanding basic results
- Simple visualization
- Next steps for deeper exploration

## Get Sample Data

You'll need a supernova spectrum to follow along. We recommend SN 2018bfi:

1. **Download**: [SN2018bif spectrum from WISeREP](https://www.wiserep.org/system/files/uploaded/PESSTO_SSDR1-4/SN2018bif_2018-05-12_03-09-55_ESO-NTT_EFOSC2-NTT_PESSTO_SSDR1-4.csv)
2. **Save**: Create a `data/` folder and save the file there as `SN2018bif.csv`
3. **Note**: This is a CSV format spectrum from the PESSTO survey

## Step-by-Step Analysis

### Step 1: Launch SNID SAGE
```powershell
snid-sage
```

![SNID SAGE welcome screen with empty plot area and Load Spectrum button highlighted](../images/0.InitialScreen.png)

The main window opens with a clean interface ready for analysis. The toolbar at the top provides quick access to essential functions.

### Step 2: Load Your Spectrum
1. Click the **"Load Spectrum"** button (grey button at top)
2. Navigate to your `data/` folder
3. Select `SN2018bif.csv`
4. **Alternative**: You can also drag and drop the spectrum file directly onto the plot area
5. The spectrum appears in the plot area

![Loaded SN2018bif spectrum showing flux vs wavelength from 3500 to 9500 Angstroms](../images/1.LoadedSpectrum.png)

Once loaded, your spectrum appears in the main plot area. The interface shows:
- **Raw spectrum** in the main plot
- **File information** in the status bar
- **Available actions** become enabled

### Step 3: Preprocess Your Data
1. Click **"Preprocessing"** button (amber - now enabled)
2. **Right-click** for **"Quick SNID Preprocessing"** (automatic)
3. **Left-click** for **"Advanced Manual Preprocessing"** (custom settings)
4. Review the cleaned spectrum

![Preprocessed spectrum in flattened view showing continuum-removed absorption and emission features](../images/2.QuickPreprocessing_Flattened.png)

The flattened view shows the continuum-removed spectrum, making absorption and emission features more prominent. This is the direct output of preprocessing.

![Preprocessed spectrum in flux view showing cleaned spectrum ready for analysis](../images/2.QuickPreprocessing_Flux.png)

The preprocessing dialog shows your spectrum with preprocessing options:
- **Filtering**: Remove noise and artifacts
- **Rebinning**: Adjust spectral resolution
- **Continuum removal**: Normalize the spectrum
- **Apodization**: Smooth spectral edges

You can switch to the flux view by clicking the **Flux** button in the top-left corner.

### Step 4: Run Analysis
1. Click **"SNID Analysis"** button (magenta - now enabled)
2. **Right-click** for **default quick analysis**
3. **Left-click** for **specific analysis settings**
4. Wait 10-30 seconds for analysis to complete

![Analysis progress dialog at 36% showing template loading phase](../images/3.AnalysisProgress1.png)
![Analysis complete dialog showing all template types processed with checkmarks](../images/3.AnalysisProgress2.png)

The analysis dialog shows:
- **Progress bar**: Current analysis stage
- **Status messages**: What's happening
- **Cancel button**: Stop analysis if needed

5. Results appear automatically

### Step 5: Choose Your Cluster (If Available)
If SNID SAGE finds multiple viable clusters, a **Cluster Selection Dialog** will appear:

![GMM cluster selection dialog with 3D redshift-type-correlation plot and top template matches](../images/4.Clustering.png)

What you'll see:
- **3D Interactive Plot**: Shows all clusters in redshift vs type vs correlation space
- **Cluster Dropdown**: Click "▼ Select Cluster" in top-left to see all options
- **Top Matches Panel**: Right side shows spectrum overlays for the selected cluster
- **Automatic Selection**: Best cluster is pre-selected (marked with BEST)

How to choose:
- **Hover** over clusters to highlight them
- **Click** on any cluster to select it
- **Use dropdown** to see all clusters with their types and redshifts
- **Review matches** in the right panel to see template quality
- **Click "Confirm Selection"** when satisfied

Tips:
- **Best cluster is usually correct** - the automatic selection is reliable
- **Check the matches panel** - better template overlays indicate better classification
- **Close dialog** to use automatic selection if unsure
- **Multiple clusters** often indicate ambiguous cases (e.g., II vs TDE)

## Understanding Your Results

The analysis provides a clear classification:

![Classification result showing Type II IIP match with input spectrum and template sn1999em overlay](../images/5.MatchTemplateFlux.png)

This view shows your spectrum overlaid with the best-matching template:
- **Your spectrum** (blue line)
- **Best template** (red line)
- **Match quality** indicators
- **Redshift information**

![Analysis results summary showing Type II IIP classification with ranked template matches and scores](../images/6.MatchSummary.png)

The summary provides:
- **Top matches** with scores
- **Spectral classification**
- **Redshift estimates**
- **Confidence levels**

Final classification:
- **Type**: Main supernova type (e.g., II, Ia, Ib, Ic)
- **Quality**: High/Medium/Low confidence level
- **Subtype**: Detailed classification (e.g., IIn, IIP, norm)

Measurements:
- **Redshift**: Determined redshift with uncertainty
- **Age**: Days from maximum light with uncertainty

Template matches:
A ranked list of best matching templates showing:
- Template name and type
- HσLAP-CCC score (final metric)
- Individual redshift and age estimates

![Scatter plot of redshift vs age distribution colored by subtype showing IIP, IIn, IIb clusters](../images/7.RedshiftVsAge.png)

This plot shows:
- **Redshift distribution** across templates
- **Age estimates** for different redshifts
- **Confidence regions**
- **Best-fit parameters**

![Subtype distribution pie chart showing IIP dominant at 58% with proportion vs threshold plot](../images/8.Subtypes.png)

The subtype analysis reveals:
- **Detailed classifications**
- **Subtype proportions**
- **Template contributions**
- **Classification confidence**

## Basic Visualization

- **Zoom**: Mouse wheel or box selection
- **Pan**: Click and drag
- **Reset View**: Double-click
- **Toggle Views**: Switch between flux and flattened views

## Quick Tips

- **Keyboard Shortcuts**: 
  - `Ctrl+O` - Load spectrum
  - `Ctrl+Enter` - Quick preprocessing + analysis
- **Button Colors**: Grey → Amber → Magenta → Purple (workflow progression)
- **Status Bar**: Check for progress updates and messages

## CLI Analysis (Alternative Method)

Prefer the command line? The CLI produces identical results with a single command:

```powershell
sage data\SN2018bif.csv --output-dir results\
```

Common options:

```powershell
sage data\SN2018bif.csv --output-dir results\ --complete      # All outputs + plots
sage data\SN2018bif.csv --output-dir results\ --minimal       # Summary only
sage data\SN2018bif.csv --output-dir results\ --forced-redshift 0.02435
sage data\SN2018bif.csv --output-dir results\ --type-filter Ia II
```

| GUI | CLI |
|-----|-----|
| Interactive cluster selection | Automatic selection |
| Step-by-step workflow | Single command |
| Display + files | Files only |

See the [CLI Reference](../cli/command-reference.md) for all options.

## Next Steps

Now that you've completed your first analysis, explore:

- **[GUI Complete Guide](../gui/interface-overview.md)** - All interface features
- **[CLI Reference](../cli/command-reference.md)** - Command-line interface
- **[AI Features](../ai/overview.md)** - AI-powered analysis

## Need Help?

- **Buttons disabled?** Follow the workflow: Load → Preprocess → Analyze
- **Poor results?** Check signal-to-noise and wavelength coverage
- **More help**: See [Troubleshooting](../reference/troubleshooting.md)

## Congratulations!

You've successfully completed your first SNID SAGE analysis! You can now:
- Load and analyze supernova spectra
- Interpret basic classification results
- Use the GUI interface effectively
- Generate basic visualizations

Ready for more? Check out our [GUI Complete Guide](../gui/interface-overview.md) for advanced features and techniques.
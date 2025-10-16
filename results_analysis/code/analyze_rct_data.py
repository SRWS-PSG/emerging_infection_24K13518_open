import os
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import numpy as np
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend for saving figures
    import matplotlib.pyplot as plt
except Exception as _plot_err:  # Continue even if matplotlib is unavailable
    plt = None

def load_data(filepath):
    """Load analysis data from CSV."""
    df = pd.read_csv(filepath)
    
    # Exclude rows for the test participant
    original_rows = len(df)
    df = df[df['participant_name'] != 'テスト用']
    if len(df) < original_rows:
        print(f"--- Preprocessing: excluded {original_rows - len(df)} 'test' participant rows. ---")
    
    # Convert '石金チェック' column to 'accuracy' (1 => 1, blanks/others => NaN)
    if '石金チェック' in df.columns:
        df['accuracy'] = pd.to_numeric(df['石金チェック'], errors='coerce')
        df.loc[df['accuracy'] != 1, 'accuracy'] = np.nan  # treat non-1 as missing
        print(f"--- Transform: converted '石金チェック' to 'accuracy' (non-1 => missing). ---")
    else:
        print("--- Warning: column '石金チェック' not found. Treating accuracy as missing. ---")
        df['accuracy'] = np.nan

    # Select necessary columns and rename
    df_processed = df[['participant_name', 'paper_id', 'has_summary', 'answer_time', 'accuracy']].copy()
    df_processed.rename(columns={
        'participant_name': 'participant_id',
        'answer_time': 'time_taken_sec'
    }, inplace=True)
    
    # Convert 'has_summary' (boolean) to 'condition' (string)
    df_processed['condition'] = df_processed['has_summary'].apply(lambda x: 'LLM' if x else 'No_LLM')
    
    # Drop the now-unneeded 'has_summary' column
    df_processed.drop(columns=['has_summary'], inplace=True)
    
    # Check/convert data types
    df_processed['time_taken_sec'] = pd.to_numeric(df_processed['time_taken_sec'], errors='coerce')
    df_processed.dropna(subset=['time_taken_sec'], inplace=True)

    df_processed['paper_id'] = df_processed['paper_id'].astype(str)

    return df_processed

def analyze_primary_outcome(df):
    """Analyze the primary outcome (time) using a linear mixed model."""
    print("\n--- Primary outcome (Linear Mixed Model) ---")
    print("Outcome: time_taken_sec (continuous)")
    model = smf.mixedlm("time_taken_sec ~ condition", df, 
                        groups=df["participant_id"], 
                        re_formula="~1",
                        vc_formula={"paper_id": "0 + C(paper_id)"})
    result = model.fit()
    print(result.summary())
    return result

def analyze_secondary_outcome(df):
    """Analyze the secondary outcome (accuracy) using a logistic GLM."""
    # Exclude rows with missing accuracy
    df_acc = df.dropna(subset=['accuracy'])
    print(f"\n--- Secondary outcome (GLM - logistic) ---")
    print(f"Outcome: accuracy (binary) - valid N: {len(df_acc)}")
    
    if len(df_acc) < 2:
        print("Insufficient valid accuracy data; skipping analysis.")
        return None

    df_acc['condition_dummy'] = df_acc['condition'].apply(lambda x: 1 if x == 'No_LLM' else 0)
    X = sm.add_constant(df_acc['condition_dummy'])
    y = df_acc['accuracy']
    
    model = sm.GLM(y, X, family=sm.families.Binomial())
    result = model.fit()
    
    print(result.summary())
    return result

def interpret_primary_result(result):
    """
    主要アウトカムの結果を解釈し、結論をプリントする。
    """
    p_value = result.pvalues['condition[T.No_LLM]']
    coef = result.params['condition[T.No_LLM]']
    conf_int = result.conf_int().loc['condition[T.No_LLM]']

    print("\n--- Interpretation (LMM) ---")
    print(f"p-value (No_LLM vs LLM) for time: {p_value:.3f}")
    print(f"Estimated difference: {coef:.1f} sec ({coef/60:.1f} min)")
    print(f"95% CI: [{conf_int[0]:.1f}, {conf_int[1]:.1f}] sec")

def interpret_secondary_result(result, df):
    """Interpret secondary outcome (accuracy) and print conclusions."""
    if result is None:
        return
        
    df_acc = df.dropna(subset=['accuracy'])
    p_value = result.pvalues['condition_dummy']
    coef = result.params['condition_dummy']
    odds_ratio = np.exp(coef)
    conf_int = np.exp(result.conf_int().loc['condition_dummy'])

    print("\n--- Interpretation (GLM) ---")
    
    accuracy_stats = df_acc.groupby('condition')['accuracy'].agg(['mean', 'sum', 'count'])
    print("Accuracy descriptive stats:")
    print(accuracy_stats)
    
    print(f"\np-value (No_LLM vs LLM) for accuracy: {p_value:.3f}")
    print(f"Odds ratio: {odds_ratio:.2f}")
    print(f"95% CI (odds ratio): [{conf_int[0]:.2f}, {conf_int[1]:.2f}]")

def generate_descriptive_table(df):
    """Generate a Markdown table of descriptive statistics."""
    print("\n--- Descriptive statistics table ---")
    desc_stats = df.groupby('condition')['time_taken_sec'].agg(['count', 'mean', 'std', 'median', 'min', 'max'])
    desc_stats.rename(columns={'count': 'N', 'mean': 'Mean time (sec)', 'std': 'SD (sec)', 'median': 'Median (sec)', 'min': 'Min (sec)', 'max': 'Max (sec)'}, inplace=True)
    desc_stats['Mean time (min)'] = desc_stats['Mean time (sec)'] / 60
    desc_stats = desc_stats[['N', 'Mean time (sec)', 'Mean time (min)', 'SD (sec)', 'Median (sec)', 'Min (sec)', 'Max (sec)']]
    print("The table below summarizes descriptive stats for task time.")
    # Fallback if 'tabulate' is not installed
    try:
        print(desc_stats.round(1).to_markdown(index=True))
    except Exception:
        print("(Note) 'tabulate' not installed; printing text table.")
        print(desc_stats.round(1).to_string(index=True))

def plot_primary_outcome(df, output_path: str = "figures/fig1_time_by_condition.png"):
    """
    Plot distribution of primary outcome (time_taken_sec) by condition.
    - Boxplots by condition with means
    - Overlay jittered individual observations
    Save as PNG.
    """
    if plt is None:
        print("Warning: matplotlib unavailable; skipping plot.")
        return None

    # Prepare data (convert sec to minutes)
    groups = ["LLM", "No_LLM"]
    data_to_plot = [
        (df.loc[df["condition"] == g, "time_taken_sec"].dropna().values / 60.0) for g in groups
    ]

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 5), dpi=120)
    # Boxplot with mean markers
    mean_props = dict(marker='D', markerfacecolor='black', markersize=5)
    bp = ax.boxplot(
        data_to_plot,
        tick_labels=groups,
        showmeans=True,
        meanprops=mean_props,
        patch_artist=True,
    )

    # Light fill colors
    colors = ["#d0e3ff", "#ffd9d0"]
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)

    # Overlay jittered points
    rng = np.random.default_rng(42)
    for i, g in enumerate(groups, start=1):
        y = (df.loc[df["condition"] == g, "time_taken_sec"].dropna().values / 60.0)
        if len(y) == 0:
            continue
        x = rng.normal(loc=i, scale=0.04, size=len(y))
        ax.plot(x, y, 'o', alpha=0.6, markersize=4, color="#333333")

    # Labels and title
    ax.set_title("Task completion time using LLM versus without LLM")
    ax.set_ylabel("Time (minutes)")

    # y-axis starts at 0
    try:
        max_val = 0.0
        for arr in data_to_plot:
            if len(arr) > 0:
                max_val = max(max_val, float(np.nanmax(arr)))
        upper = max_val * 1.10 if max_val > 0 else 1.0
        ax.set_ylim(0, upper)
    except Exception:
        # Fallback: at least set lower bound to 0
        ax.set_ylim(bottom=0)

    # Optional: add minute ticks on right-hand axis
    # sec_to_min = lambda s: s / 60.0
    # sec_lims = ax.get_ylim()
    # min_ticks = np.linspace(sec_lims[0], sec_lims[1], 6)
    # ax2 = ax.twinx()
    # ax2.set_ylim(sec_lims)
    # ax2.set_yticks(min_ticks)
    # ax2.set_yticklabels([f"{t/60:.1f}" for t in min_ticks])
    # ax2.set_ylabel("Time (minutes)")

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved figure: {output_path}")


if __name__ == "__main__":
    data_filepath = "Systematic Review - Results Database - Results (1).csv"
    try:
        df = load_data(data_filepath)
        if df.empty:
            print("No valid data. Exiting.")
        else:
            # --- Complete-case analysis ---
            # Analyze only rows with non-missing accuracy
            df_complete = df.dropna(subset=['accuracy'])
            print(f"\n--- Complete-case: analyzing {len(df_complete)} records with valid accuracy ---")

            print("\n--- Data overview (complete cases) ---")
            print(df_complete.describe())
            
            generate_descriptive_table(df_complete)
            
            primary_result = analyze_primary_outcome(df_complete)
            interpret_primary_result(primary_result)

            secondary_result = analyze_secondary_outcome(df_complete)
            interpret_secondary_result(secondary_result, df_complete)

            # Plot (primary outcome: time distribution by condition)
            plot_primary_outcome(df_complete, output_path="figures/fig1_time_by_condition.png")

            print("\nAnalysis completed.")
    except FileNotFoundError:
        print(f"Error: data file '{data_filepath}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

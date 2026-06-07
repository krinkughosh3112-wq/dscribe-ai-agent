# main.py
import json
import os
from pathlib import Path
from datetime import datetime
from src.agent import DischargeSummaryAgent

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║     🏥  DSCRIBE - AI Discharge Summary Agent  🏥             ║
    ║                                                              ║
    ║     Turning messy clinical notes into structured            ║
    ║     discharge summaries with clinical safety                ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Create output directories
    Path("outputs").mkdir(exist_ok=True)
    Path("traces").mkdir(exist_ok=True)
    
    # Find PDFs in data folder
    data_folder = Path("data")
    
    if not data_folder.exists():
        print("❌ 'data' folder not found!")
        print("   Creating 'data' folder...")
        data_folder.mkdir(exist_ok=True)
        print("   ✅ Please add your patient PDF files to the 'data' folder")
        return
    
    pdf_files = list(data_folder.glob("*.pdf")) + list(data_folder.glob("*.txt"))
    
    if not pdf_files:
        print("❌ No PDF files found in 'data/' folder!")
        print("   📁 Please add your patient PDF(s) to the 'data' folder")
        print("\n   Example:")
        print("   data/")
        print("   ├── patient_1.pdf")
        print("   └── patient_2.pdf")
        return
    
    print(f"\n📁 Found {len(pdf_files)} patient PDF(s):")
    for pdf in pdf_files:
        print(f"   - {pdf.name}")
    
    print("\n" + "="*60)
    print("Starting agent execution...")
    print("="*60)
    
    # Initialize agent
    agent = DischargeSummaryAgent(max_iterations=10)
    
    # Process each patient
    all_results = {}
    
    for pdf_path in pdf_files:
        print(f"\n{'#'*60}")
        print(f"🏥 PROCESSING: {pdf_path.stem}")
        print(f"{'#'*60}")
        
        try:
            results = agent.run(str(pdf_path))
            all_results[pdf_path.stem] = results
            
            # Save outputs
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save discharge summary
            summary_path = f"outputs/{pdf_path.stem}_{timestamp}_summary.txt"
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(results['discharge_summary'])
            
            # Save trace
            trace_path = f"traces/{pdf_path.stem}_{timestamp}_trace.json"
            with open(trace_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "trace": results['trace'],
                    "state": results['state'],
                    "stats": results['stats'],
                    "safety_checks": results['safety_checks']
                }, f, indent=2)
            
            print(f"\n✅ Results saved:")
            print(f"   📄 Summary: {summary_path}")
            print(f"   📊 Trace: {trace_path}")
            
            # Print summary stats
            print(f"\n📈 STATISTICS:")
            print(f"   - Iterations used: {results['stats']['iterations']}")
            print(f"   - Flags raised: {results['stats']['flags_count']}")
            print(f"   - Conflicts found: {results['stats']['conflicts_count']}")
            print(f"   - Pending items: {results['stats']['pending_count']}")
            print(f"   - Diagnoses found: {results['stats']['diagnoses_count']}")
            
            # Print safety check results
            print(f"\n🛡️ SAFETY CHECKS:")
            for check, passed in results['safety_checks'].items():
                status = "✅ PASS" if passed else "⚠️ CHECK"
                print(f"   - {check}: {status}")
            
        except Exception as e:
            print(f"\n❌ Error processing {pdf_path.name}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("🎉 ALL PATIENTS PROCESSED SUCCESSFULLY!")
    print(f"{'='*60}")
    print("\n📁 Outputs saved to:")
    print("   - outputs/     : Discharge summaries (text files)")
    print("   - traces/      : Agent execution traces (JSON files)")
    print("\n💡 Next steps:")
    print("   - Review the discharge summaries in 'outputs/' folder")
    print("   - Check traces to see agent's reasoning")
    print("   - Run 'streamlit run app.py' for web interface")

if __name__ == "__main__":
    main()
import sys,importlib.util,unittest,subprocess,json
sys.path.insert(0,'/app')
print(json.dumps({'scope':'Matched original production source tree in prior clean validated checkout; same external control as candidate','commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'production_baseline_commit':'769bf99ee719f5e353822cdbd75b9259c8fd5fe1'}),flush=True)
spec=importlib.util.spec_from_file_location('restoration_control','/evidence/restoration-control.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(m));raise SystemExit(0 if r.wasSuccessful() else 1)

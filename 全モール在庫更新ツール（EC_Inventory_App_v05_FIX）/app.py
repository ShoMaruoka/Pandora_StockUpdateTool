from __future__ import annotations
import json, os, subprocess, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from engine import precheck, run_all, validate_inputs

APP_NAME="EC在庫更新アプリ Ver0.5"
CONFIG=Path.home()/".ec_inventory_app_config_v04.json"

FIELDS=[
 ("wholesale","① 卸会社在庫（xlsm）",[("Excel","*.xlsm *.xlsx")]),
 ("logiless","② LOGILESS / T2K在庫（csv）",[("CSV","*.csv")]),
 ("ir_item","③ itemRobot ir-item.csv",[("CSV","*.csv")]),
 ("ir_selection","④ itemRobot ir-selection.csv",[("CSV","*.csv")]),
 ("ir_itemsub","⑤ itemRobot ir-itemsub_楽天.csv",[("CSV","*.csv")]),
 ("amazon_report","⑥ Amazon 出品中の商品レポート",[("TXT/CSV","*.txt *.csv")]),
 ("amazon_template","⑦ Amazon PriceAndQuantity.xlsm",[("Excel","*.xlsm")]),
 ("mercari","⑧ メルカリ product_data.csv",[("CSV","*.csv")]),
 ("quote_master","⑨ 見積り商品構成マスター（任意）",[("Excel/CSV","*.xlsx *.xlsm *.csv")]),
]

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1120x820")
        self.minsize(1020,720)
        self.vars={k:tk.StringVar() for k,_,_ in FIELDS}
        self.out=tk.StringVar(value=str(Path.home()/"Desktop"/"EC在庫更新出力"))
        self.ch_item=tk.BooleanVar(value=True)
        self.ch_amz=tk.BooleanVar(value=True)
        self.ch_mer=tk.BooleanVar(value=True)
        self.status=tk.StringVar(value="ファイルを選択してください。")
        self.last_check=None
        self._load()
        self._build()

    def _build(self):
        style=ttk.Style(self)
        try: style.theme_use("vista")
        except Exception: pass
        style.configure("Title.TLabel",font=("Yu Gothic UI",18,"bold"))
        style.configure("Big.TButton",font=("Yu Gothic UI",11,"bold"),padding=8)

        top=ttk.Frame(self)
        top.pack(fill="x",padx=16,pady=(12,4))
        ttk.Label(top,text=APP_NAME,style="Title.TLabel").pack(anchor="w")
        ttk.Label(top,text="卸調整在庫 + T2Kフリー在庫から、楽天・Yahoo! / Amazon / メルカリ更新ファイルを一括生成").pack(anchor="w",pady=(2,0))

        notebook=ttk.Notebook(self)
        notebook.pack(fill="both",expand=True,padx=16,pady=8)

        self.tab_files=ttk.Frame(notebook)
        self.tab_check=ttk.Frame(notebook)
        self.tab_run=ttk.Frame(notebook)
        notebook.add(self.tab_files,text=" 1. ファイル選択 ")
        notebook.add(self.tab_check,text=" 2. データチェック ")
        notebook.add(self.tab_run,text=" 3. 更新ファイル作成 ")
        self.notebook=notebook

        self._build_files()
        self._build_check()
        self._build_run()

        bar=ttk.Frame(self)
        bar.pack(fill="x",padx=16,pady=(0,10))
        ttk.Label(bar,textvariable=self.status,foreground="#1F4E78").pack(side="left")

    def _build_files(self):
        files=ttk.LabelFrame(self.tab_files,text="入力ファイル")
        files.pack(fill="both",expand=True,padx=12,pady=12)
        for row,(key,label,types) in enumerate(FIELDS):
            ttk.Label(files,text=label,width=36).grid(row=row,column=0,sticky="w",padx=8,pady=5)
            ttk.Entry(files,textvariable=self.vars[key]).grid(row=row,column=1,sticky="ew",padx=8,pady=5)
            ttk.Button(files,text="参照",command=lambda k=key,t=types:self.pick(k,t),width=10).grid(row=row,column=2,padx=8,pady=5)
        files.columnconfigure(1,weight=1)

        outrow=len(FIELDS)
        ttk.Separator(files).grid(row=outrow,column=0,columnspan=3,sticky="ew",pady=8)
        ttk.Label(files,text="出力先フォルダ",width=36).grid(row=outrow+1,column=0,sticky="w",padx=8,pady=5)
        ttk.Entry(files,textvariable=self.out).grid(row=outrow+1,column=1,sticky="ew",padx=8,pady=5)
        ttk.Button(files,text="参照",command=self.pick_out,width=10).grid(row=outrow+1,column=2,padx=8,pady=5)

        opts=ttk.LabelFrame(files,text="出力対象")
        opts.grid(row=outrow+2,column=0,columnspan=3,sticky="ew",padx=8,pady=10)
        ttk.Checkbutton(opts,text="楽天・Yahoo!（itemRobot）",variable=self.ch_item).pack(side="left",padx=16,pady=8)
        ttk.Checkbutton(opts,text="Amazon",variable=self.ch_amz).pack(side="left",padx=16,pady=8)
        ttk.Checkbutton(opts,text="メルカリ",variable=self.ch_mer).pack(side="left",padx=16,pady=8)

        ttk.Button(files,text="次へ：データチェック",style="Big.TButton",command=self.go_check).grid(row=outrow+3,column=1,sticky="e",padx=8,pady=12)

        rule=ttk.LabelFrame(self.tab_files,text="SKU判定ルール")
        rule.pack(fill="x",padx=12,pady=(0,12))
        ttk.Label(rule,text="6桁=そのまま　｜　xN=÷N切捨て　｜　mxN/xmN=÷N　｜　dN・/N=×N　｜　6桁-N=前6桁WebCD　｜　7桁数字=見積りコードで除外",
                  wraplength=1040).pack(anchor="w",padx=10,pady=8)

    def _build_check(self):
        head=ttk.Frame(self.tab_check)
        head.pack(fill="x",padx=12,pady=10)
        ttk.Button(head,text="データチェック実行",style="Big.TButton",command=self.check).pack(side="left")
        ttk.Button(head,text="ファイル選択へ戻る",command=lambda:self.notebook.select(self.tab_files)).pack(side="left",padx=8)

        self.summary=tk.Text(self.tab_check,height=15,wrap="word",font=("Yu Gothic UI",10))
        self.summary.pack(fill="both",expand=True,padx=12,pady=(0,8))
        self.summary.configure(state="disabled")

        warn=ttk.LabelFrame(self.tab_check,text="安全ルール")
        warn.pack(fill="x",padx=12,pady=(0,12))
        ttk.Label(warn,text="未一致・未定義・7桁見積りコードは元在庫を保持します。在庫0へ自動変換しません。"
                            "また、旧在庫から80%以上減るSKUは「急減警告」としてチェック画面に表示します。",
                  wraplength=1030).pack(anchor="w",padx=10,pady=8)

        ttk.Button(self.tab_check,text="次へ：更新ファイル作成",style="Big.TButton",
                   command=lambda:self.notebook.select(self.tab_run)).pack(anchor="e",padx=14,pady=(0,12))

    def _build_run(self):
        frm=ttk.Frame(self.tab_run)
        frm.pack(fill="both",expand=True,padx=20,pady=20)
        ttk.Label(frm,text="更新ファイルを作成します",font=("Yu Gothic UI",15,"bold")).pack(anchor="w")
        ttk.Label(frm,text="実行ごとに日時付きフォルダを自動作成するため、前回の更新ファイルを上書きしません。").pack(anchor="w",pady=(4,18))

        ttk.Button(frm,text="更新ファイルを作成",style="Big.TButton",command=self.run).pack(anchor="w")
        ttk.Button(frm,text="出力フォルダを開く",command=self.open_out).pack(anchor="w",pady=10)

        ttk.Label(frm,text="作成ファイル",font=("Yu Gothic UI",11,"bold")).pack(anchor="w",pady=(20,5))
        text=("・統合在庫マスター_YYYYMMDD.csv\n"
              "・ir-item_在庫更新_YYYYMMDD.csv\n"
              "・ir-selection_在庫更新_YYYYMMDD.csv\n"
              "・Amazon_PriceAndQuantity_YYYYMMDD.xlsm\n"
              "・Amazon在庫更新_YYYYMMDD.txt\n"
              "・メルカリ在庫更新_YYYYMMDD.csv\n"
              "・在庫更新監査_YYYYMMDD.csv\n"
              "・欠品商品_YYYYMMDD.csv（新規欠品／継続欠品／欠品解消）\n"
              "・販売SKU欠品_YYYYMMDD.csv\n"
              "・要確認SKU_YYYYMMDD.csv")
        ttk.Label(frm,text=text,justify="left").pack(anchor="w")

        self.run_result=tk.Text(frm,height=10,wrap="word",font=("Yu Gothic UI",10))
        self.run_result.pack(fill="both",expand=True,pady=(16,0))
        self.run_result.configure(state="disabled")

    def channels(self):
        c=[]
        if self.ch_item.get(): c.append("itemrobot")
        if self.ch_amz.get(): c.append("amazon")
        if self.ch_mer.get(): c.append("mercari")
        return c

    def pick(self,key,types):
        p=filedialog.askopenfilename(filetypes=types+[("すべてのファイル","*.*")])
        if p:self.vars[key].set(p)

    def pick_out(self):
        p=filedialog.askdirectory()
        if p:self.out.set(p)

    def inputs(self): return {k:v.get() for k,v in self.vars.items()}

    def go_check(self):
        self.notebook.select(self.tab_check)
        self.check()

    def set_text(self,widget,text):
        widget.configure(state="normal")
        widget.delete("1.0","end")
        widget.insert("1.0",text)
        widget.configure(state="disabled")

    def check(self):
        try:
            errs,warns=validate_inputs(self.inputs(),self.channels())
            if errs:
                self.set_text(self.summary,"【入力エラー】\n"+"\n".join("・"+x for x in errs))
                self.status.set("入力ファイルに問題があります。")
                messagebox.showerror("入力エラー","入力ファイルを確認してください。")
                return
            self.status.set("照合中…")
            self.update_idletasks()
            r=precheck(self.inputs(),self.channels())
            self.last_check=r
            s=r["summary"]; a=r["analysis"]
            lines=[
                "【全体】",
                f"卸在庫 使用シート：{r['sheet']}",
                f"統合WebCD数：{r['master_count']:,}",
                f"見積り7桁 登録数：{r.get('quote_count',0):,}",
                f"照合対象SKU：{s['total']:,}",
                f"自動照合OK：{s['ok']:,}",
                f"在庫変更予定：{s['changed']:,}",
                "",
                "【モール別】",
            ]
            for ch,stats in a["status_by_channel"].items():
                total=sum(stats.values()); ok=stats.get("OK",0)
                lines.append(f"■ {ch}：{ok:,} / {total:,} OK")
                for st,n in sorted(stats.items()):
                    if st!="OK":
                        lines.append(f"   ・{st}: {n:,}")
            severe=a["severe_drops"]
            lines += ["",f"【急減警告（80%以上減少）】 {len(severe):,}件"]
            for x in severe[:30]:
                lines.append(f"・{x['channel']} / {x['sku']}：{x['old_stock']} → {x['new_stock']}（-{x['drop_pct']}%）")
            if len(severe)>30:
                lines.append(f"…ほか {len(severe)-30:,}件")
            if warns or r["warnings"]:
                lines += ["","【入力警告】"] + [f"・{x}" for x in warns+r["warnings"][:20]]
            lines += ["","※ OK以外は元在庫を保持します。更新後は「要確認SKU」CSVでも確認できます。"]
            self.set_text(self.summary,"\n".join(lines))
            self.status.set("チェック完了。内容を確認してください。")
        except Exception as e:
            self.status.set("チェックエラー")
            messagebox.showerror("チェックエラー",str(e))

    def run(self):
        try:
            errs,_=validate_inputs(self.inputs(),self.channels())
            if errs:
                messagebox.showerror("入力エラー","先にデータチェックを行ってください。")
                return
            if self.last_check is None:
                if not messagebox.askyesno("確認","まだデータチェックを実行していません。\n先にチェックしますか？"):
                    return
                self.check()
                if self.last_check is None:return

            severe=len(self.last_check.get("analysis",{}).get("severe_drops",[]))
            msg="現在のデータから更新ファイルを作成します。"
            if severe:
                msg+=f"\n\n急減警告が {severe}件 あります。\n監査CSVで確認してください。"
            msg+="\n\n実行しますか？"
            if not messagebox.askyesno("最終確認",msg):return

            self.status.set("更新ファイル作成中…")
            self.update_idletasks()
            o=run_all(self.inputs(),self.out.get(),self.channels(),create_run_folder=True)
            self._save()
            s=o["summary"]; a=o["analysis"]
            text=(f"作成完了\n\n出力フォルダ：\n{o['output_dir']}\n\n"
                  f"照合対象SKU：{s['total']:,}\n"
                  f"自動照合OK：{s['ok']:,}\n"
                  f"在庫変更：{s['changed']:,}\n"
                  f"急減警告：{len(a['severe_drops']):,}\n\n"
                  "「要確認SKU」CSVと「在庫更新監査」CSVも確認してください。")
            self.set_text(self.run_result,text)
            self.status.set("更新ファイル作成完了。")
            messagebox.showinfo("完了","更新ファイルを作成しました。")
        except Exception as e:
            self.status.set("処理エラー")
            messagebox.showerror("処理エラー",str(e))

    def open_out(self):
        p=Path(self.out.get()); p.mkdir(parents=True,exist_ok=True)
        try: os.startfile(str(p))
        except AttributeError: subprocess.Popen(["xdg-open",str(p)])

    def _load(self):
        try:
            d=json.loads(CONFIG.read_text(encoding="utf-8"))
            self.out.set(d.get("out",self.out.get()))
        except Exception: pass

    def _save(self):
        try:
            CONFIG.write_text(json.dumps({"out":self.out.get()},ensure_ascii=False),encoding="utf-8")
        except Exception: pass

if __name__=="__main__":
    App().mainloop()

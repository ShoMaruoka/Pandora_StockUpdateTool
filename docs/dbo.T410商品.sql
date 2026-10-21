SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[T410商品](
	[商品CD] [varchar](13) NOT NULL,
	[カタログCD] [varchar](5) NULL,
	[品目区分CD] [varchar](4) NULL,
	[商品名] [nvarchar](25) NOT NULL,
	[商品名カナ] [nvarchar](50) NULL,
	[規格] [nvarchar](20) NULL,
	[メ型番] [varchar](20) NULL,
	[単位] [nvarchar](3) NULL,
	[入数] [smallint] NULL,
	[内箱入数] [smallint] NULL,
	[最低受注数] [smallint] NULL,
	[直送発注単位数] [smallint] NULL,
	[倉入発注ロット数] [smallint] NOT NULL,
	[倉入最低発注数] [smallint] NOT NULL,
	[出荷時個口数] [smallint] NOT NULL,
	[送料無料出荷数] [smallint] NULL,
	[送料無料補足] [nvarchar](100) NULL,
	[課税区分] [tinyint] NOT NULL,
	[単価設定] [tinyint] NOT NULL,
	[価格改訂日] [smalldatetime] NULL,
	[小売価格] [money] NOT NULL,
	[小売参考区分] [tinyint] NOT NULL,
	[販売単価] [money] NOT NULL,
	[最低販売単価] [money] NOT NULL,
	[原単価] [money] NOT NULL,
	[倉庫入原単価] [money] NOT NULL,
	[本原単価] [money] NOT NULL,
	[本倉庫入原単価] [money] NOT NULL,
	[WEB掲載価格] [money] NOT NULL,
	[WEB掲載価格掛率] [money] NULL,
	[ランク対象外] [tinyint] NOT NULL,
	[倉入発注ロット数修正可] [smallint] NOT NULL,
	[倉入最低発注数修正可] [smallint] NOT NULL,
	[仕入先CD] [smallint] NULL,
	[MAKERCD] [smallint] NULL,
	[定番在庫] [tinyint] NOT NULL,
	[送料無料] [tinyint] NOT NULL,
	[送料対象] [tinyint] NOT NULL,
	[送料実費] [tinyint] NOT NULL,
	[一律送料] [tinyint] NOT NULL,
	[送料] [nvarchar](25) NULL,
	[特定福祉用具] [tinyint] NOT NULL,
	[住宅改修] [tinyint] NOT NULL,
	[管理医療区分] [tinyint] NOT NULL,
	[アウトレット] [tinyint] NOT NULL,
	[直送不可] [tinyint] NOT NULL,
	[個人宅直送不可] [tinyint] NOT NULL,
	[病院施設直送不可] [tinyint] NOT NULL,
	[バラ販売可] [tinyint] NOT NULL,
	[危険物] [tinyint] NOT NULL,
	[受注生産品] [tinyint] NOT NULL,
	[賞味期限商品] [tinyint] NOT NULL,
	[使用期限商品] [tinyint] NOT NULL,
	[使用期限日] [smallint] NULL,
	[都度見積商品] [tinyint] NOT NULL,
	[一体資産] [tinyint] NOT NULL,
	[検定付] [tinyint] NOT NULL,
	[直送切替中] [tinyint] NOT NULL,
	[返品不可] [tinyint] NOT NULL,
	[廃棄返品] [tinyint] NOT NULL,
	[在庫管理区分] [tinyint] NOT NULL,
	[在庫適正数110] [smallint] NULL,
	[在庫適正数120] [smallint] NULL,
	[在庫適正数130] [smallint] NULL,
	[在庫適正数150] [smallint] NULL,
	[在庫適正数111] [smallint] NULL,
	[在庫適正数405] [smallint] NULL,
	[在庫適正数170] [smallint] NULL,
	[在庫適正数180] [smallint] NULL,
	[在庫適正数190] [smallint] NULL,
	[在庫適正数400] [smallint] NULL,
	[在庫適正数440] [smallint] NULL,
	[優先引当] [tinyint] NOT NULL,
	[時間帯直送] [tinyint] NOT NULL,
	[最低発注数110] [smallint] NOT NULL,
	[最低発注数120] [smallint] NOT NULL,
	[最低発注数130] [smallint] NOT NULL,
	[最低発注数150] [smallint] NOT NULL,
	[最低発注数111] [smallint] NOT NULL,
	[最低発注数405] [smallint] NOT NULL,
	[最低発注数170] [smallint] NOT NULL,
	[最低発注数180] [smallint] NOT NULL,
	[最低発注数190] [smallint] NOT NULL,
	[最低発注数400] [smallint] NOT NULL,
	[最低発注数440] [smallint] NOT NULL,
	[部品] [tinyint] NOT NULL,
	[ラッピング通常] [tinyint] NOT NULL,
	[ラッピング杖] [tinyint] NOT NULL,
	[欠品情報] [nvarchar](25) NULL,
	[欠品解除日] [smalldatetime] NULL,
	[受注停止] [tinyint] NOT NULL,
	[廃盤情報] [nvarchar](25) NULL,
	[デモ機情報] [nvarchar](30) NULL,
	[入力喚起] [nvarchar](40) NULL,
	[入力喚起期限] [smalldatetime] NULL,
	[WEB販売] [tinyint] NOT NULL,
	[個人宅送料要] [tinyint] NOT NULL,
	[取扱開始日] [varchar](8) NOT NULL,
	[取扱終了日] [varchar](8) NOT NULL,
	[最終販売日] [smalldatetime] NULL,
	[最終仕入日] [smalldatetime] NULL,
	[TAIS] [varchar](12) NULL,
	[販売マーク有無] [tinyint] NOT NULL,
	[貸与マーク有無] [tinyint] NOT NULL,
	[JAN] [varchar](13) NULL,
	[医療機器認証番号] [varchar](18) NULL,
	[WELFANCD] [varchar](6) NULL,
	[GUTTCD] [varchar](5) NULL,
	[原産国] [nvarchar](10) NULL,
	[WEB画像取得] [tinyint] NOT NULL,
	[備考] [nvarchar](60) NULL,
	[事務共有備考] [nvarchar](150) NULL,
	[デモ機サンプル備考] [nvarchar](50) NULL,
	[カタログ除外予定日] [smalldatetime] NULL,
	[サイズ160] [tinyint] NOT NULL,
	[サイズ200] [tinyint] NOT NULL,
	[サイズ240] [tinyint] NOT NULL,
	[サイズ] [smallint] NULL,
	[WebCD] [int] NULL,
	[登録日] [datetime] NULL,
	[登録者] [nvarchar](10) NULL,
	[更新日] [datetime] NULL,
	[更新者] [nvarchar](10) NULL,
	[WEB用更新日] [datetime] NULL,
 CONSTRAINT [PK_T410商品] PRIMARY KEY NONCLUSTERED 
(
	[商品CD] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY],
 CONSTRAINT [IX_T410商品_WebCD] UNIQUE NONCLUSTERED 
(
	[WebCD] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
CREATE CLUSTERED INDEX [IX_T410商品_SORT] ON [dbo].[T410商品]
(
	[商品CD] ASC,
	[商品名] ASC,
	[規格] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
CREATE NONCLUSTERED INDEX [IX_T410商品_アウトレット] ON [dbo].[T410商品]
(
	[アウトレット] ASC
)
INCLUDE ( 	[商品CD]) WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
CREATE NONCLUSTERED INDEX [IX_T410商品_カタログCD] ON [dbo].[T410商品]
(
	[カタログCD] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
CREATE NONCLUSTERED INDEX [IX_T410商品_メ型番MAKERCD取扱終了日] ON [dbo].[T410商品]
(
	[メ型番] ASC,
	[MAKERCD] ASC,
	[取扱終了日] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
CREATE NONCLUSTERED INDEX [IX_T410商品_仕入先CD] ON [dbo].[T410商品]
(
	[仕入先CD] ASC
)
INCLUDE ( 	[商品CD],
	[カタログCD],
	[品目区分CD],
	[商品名],
	[規格],
	[メ型番],
	[単位],
	[課税区分],
	[小売価格],
	[販売単価],
	[最低販売単価],
	[原単価],
	[倉庫入原単価],
	[定番在庫],
	[送料無料],
	[送料対象],
	[送料実費],
	[一律送料],
	[特定福祉用具],
	[住宅改修],
	[アウトレット],
	[直送不可],
	[個人宅直送不可],
	[賞味期限商品],
	[使用期限商品],
	[使用期限日],
	[部品],
	[欠品情報],
	[廃盤情報],
	[デモ機情報],
	[取扱開始日],
	[TAIS],
	[WELFANCD],
	[GUTTCD],
	[WebCD]) WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
CREATE NONCLUSTERED INDEX [IX_T410商品_定番在庫] ON [dbo].[T410商品]
(
	[定番在庫] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
CREATE NONCLUSTERED INDEX [IX_T410商品_備考] ON [dbo].[T410商品]
(
	[備考] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
CREATE NONCLUSTERED INDEX [IX_T410商品_品目区分CD] ON [dbo].[T410商品]
(
	[品目区分CD] ASC
)
INCLUDE ( 	[商品CD],
	[仕入先CD]) WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
CREATE NONCLUSTERED INDEX [IX_T410商品_部品] ON [dbo].[T410商品]
(
	[部品] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_倉入発注ロット数]  DEFAULT ((1)) FOR [倉入発注ロット数]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_倉入最低発注数]  DEFAULT ((1)) FOR [倉入最低発注数]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_出荷時個口数]  DEFAULT ((1)) FOR [出荷時個口数]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_単価設定]  DEFAULT ((1)) FOR [単価設定]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_小売参考区分]  DEFAULT ((2)) FOR [小売参考区分]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低販売単価]  DEFAULT ((0)) FOR [最低販売単価]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_原単価1]  DEFAULT ((0)) FOR [倉庫入原単価]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_EDI原単価]  DEFAULT ((0)) FOR [本原単価]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_本原単価1]  DEFAULT ((0)) FOR [本倉庫入原単価]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_倉庫入原単価1]  DEFAULT ((0)) FOR [WEB掲載価格]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_ランク対象外]  DEFAULT ((2)) FOR [ランク対象外]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_倉入発注ロット数1]  DEFAULT ((1)) FOR [倉入発注ロット数修正可]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_倉入最低発注数1]  DEFAULT ((1)) FOR [倉入最低発注数修正可]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_定番在庫]  DEFAULT ((2)) FOR [定番在庫]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_送料無料]  DEFAULT ((2)) FOR [送料無料]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_送料対象]  DEFAULT ((2)) FOR [送料対象]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_送料実費]  DEFAULT ((2)) FOR [送料実費]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_一律送料]  DEFAULT ((0)) FOR [一律送料]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_特定福祉用具]  DEFAULT ((2)) FOR [特定福祉用具]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_住宅改修]  DEFAULT ((2)) FOR [住宅改修]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_管理医療区分]  DEFAULT ((0)) FOR [管理医療区分]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_アウトレット]  DEFAULT ((2)) FOR [アウトレット]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_直送不可]  DEFAULT ((2)) FOR [直送不可]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_個人宅直送不可]  DEFAULT ((2)) FOR [個人宅直送不可]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_病院施設直送不可]  DEFAULT ((2)) FOR [病院施設直送不可]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_バラ販売可]  DEFAULT ((2)) FOR [バラ販売可]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_バラ販売可1]  DEFAULT ((2)) FOR [危険物]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_受注生産品]  DEFAULT ((2)) FOR [受注生産品]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_賞味期限商品]  DEFAULT ((2)) FOR [賞味期限商品]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_使用期限商品]  DEFAULT ((2)) FOR [使用期限商品]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_都度見積商品]  DEFAULT ((2)) FOR [都度見積商品]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_一体資産]  DEFAULT ((2)) FOR [一体資産]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_一体資産1]  DEFAULT ((2)) FOR [検定付]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_直送切替中]  DEFAULT ((2)) FOR [直送切替中]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_廃棄返品1]  DEFAULT ((2)) FOR [返品不可]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_検定付1]  DEFAULT ((2)) FOR [廃棄返品]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_在庫管理区分]  DEFAULT ((1)) FOR [在庫管理区分]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_優先引当]  DEFAULT ((2)) FOR [優先引当]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_時間帯直送]  DEFAULT ((2)) FOR [時間帯直送]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数110]  DEFAULT ((1)) FOR [最低発注数110]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数1101_1]  DEFAULT ((1)) FOR [最低発注数120]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数1102]  DEFAULT ((1)) FOR [最低発注数130]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数150]  DEFAULT ((1)) FOR [最低発注数150]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数140]  DEFAULT ((1)) FOR [最低発注数111]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数1901]  DEFAULT ((1)) FOR [最低発注数405]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数1101]  DEFAULT ((1)) FOR [最低発注数170]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数1701]  DEFAULT ((1)) FOR [最低発注数180]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数1103]  DEFAULT ((1)) FOR [最低発注数190]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数4301]  DEFAULT ((1)) FOR [最低発注数400]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_最低発注数440]  DEFAULT ((1)) FOR [最低発注数440]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_部品]  DEFAULT ((2)) FOR [部品]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_ラッピング通常]  DEFAULT ((2)) FOR [ラッピング通常]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_ラッピング杖]  DEFAULT ((2)) FOR [ラッピング杖]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_ラッピング杖1]  DEFAULT ((2)) FOR [受注停止]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_WEB販売]  DEFAULT ((1)) FOR [WEB販売]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_個人宅送料要]  DEFAULT ((2)) FOR [個人宅送料要]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_販売マーク有無]  DEFAULT ((2)) FOR [販売マーク有無]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_貸与マーク有無]  DEFAULT ((2)) FOR [貸与マーク有無]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_WEB画像取得]  DEFAULT ((1)) FOR [WEB画像取得]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_サイズ160]  DEFAULT ((0)) FOR [サイズ160]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_サイズ1601_1]  DEFAULT ((0)) FOR [サイズ200]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_サイズ2001]  DEFAULT ((0)) FOR [サイズ240]
GO
ALTER TABLE [dbo].[T410商品] ADD  CONSTRAINT [DF_T410商品_サイズ1601]  DEFAULT ((0)) FOR [サイズ]
GO
ALTER TABLE [dbo].[T410商品]  WITH NOCHECK ADD  CONSTRAINT [FK_T410商品_T210品目区分] FOREIGN KEY([品目区分CD])
REFERENCES [dbo].[T210品目区分] ([品目区分CD])
GO
ALTER TABLE [dbo].[T410商品] CHECK CONSTRAINT [FK_T410商品_T210品目区分]

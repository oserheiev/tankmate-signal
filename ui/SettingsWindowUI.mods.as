      // These members extend the client's SettingsWindowUI, preserving its art
      // and all stock tab handlers. The build tool injects them into that class.
      private var tankmatePane:Sprite;
      private var tankmateInnerTabs:ButtonBarEx;
      private var tankmateKey:KeyInput;
      private var tankmateDeveloper:CheckBox;
      private var tankmateFieldSet:FieldSet;
      private var tankmateLabel:TextField;
      private var tankmateDescription:TextField;
      private var tankmateInputManager:Object;
      private var tankmateState:Object;
      private var tankmateSync:Boolean = false;
      private var tankmateCapture:Boolean = false;
      private var tankmateActive:Boolean = false;
      private var tankmateHooksReady:Boolean = false;
      private var tankmateDirty:Boolean = false;
      private static const TANKMATE_LINK:String = "tankmate.signal";
      // ViewStack is a small timeline placeholder, not the content rectangle.
      // These are the stock Settings tab dimensions in the bundled movie.
      private static const TANKMATE_CONTENT_WIDTH:Number = 802;
      private static const TANKMATE_CONTENT_HEIGHT:Number = 523;

      override protected function configUI() : void
      {
         super.configUI();
         tabs.addEventListener(IndexEvent.INDEX_CHANGE, this.onTankmateTab, false, 1000, true);
         var inputClass:Class = getDefinitionByName("scaleform.clik.managers.InputDelegate") as Class;
         this.tankmateInputManager = inputClass["getInstance"]();
         this.tankmateInputManager.addEventListener("input", this.onTankmateInput, false, 1000, true);
         addEventListener(Event.ENTER_FRAME, this.onTankmateFrame, false, 0, true);
         this.tankmateHooksReady = true;
      }

      override public function as_setData(data:Object) : void
      {
         var active:Boolean = this.tankmateActive;
         this.tankmateSync = true;
         super.as_setData(data);
         this.installTankmateTab();
         if(active)
         {
            tabs.selectedIndex = this.tankmateTabIndex();
         }
         this.tankmateSync = false;
         this.showTankmate(active);
      }

      public function as_setTankmateSettings(data:Object) : void
      {
         this.tankmateState = data;
         this.tankmateDirty = Boolean(data.dirty);
         this.tankmateCapture = Boolean(data.capturing);
         this.syncTankmateControls();
      }

      private function makeTankmateComponent(name:String) : Object
      {
         var componentClass:Class = getDefinitionByName(name) as Class;
         return new componentClass();
      }

      private function makeTankmateText() : TextField
      {
         var text:TextField = new TextField();
         var format:TextFormat = new TextFormat("$TextFont", 12, 0x969687);
         format.align = "left";
         format.leading = 2;
         text.defaultTextFormat = format;
         text.embedFonts = true;
         text.selectable = false;
         text.mouseEnabled = false;
         return text;
      }

      private function buildTankmatePane() : void
      {
         this.tankmatePane = new Sprite();
         this.tankmatePane.x = view.x;
         this.tankmatePane.y = view.y;
         this.tankmatePane.visible = false;
         // Native controls need a stage before validateNow initializes them.
         addChild(this.tankmatePane);
         var background:Object = this.makeTankmateComponent("Window_BGForm");
         background.width = TANKMATE_CONTENT_WIDTH;
         background.height = TANKMATE_CONTENT_HEIGHT;
         this.tankmatePane.addChild(background);
         this.tankmateFieldSet = this.makeTankmateComponent("FieldSet") as FieldSet;
         this.tankmateFieldSet.x = 2;
         this.tankmateFieldSet.y = 34;
         this.tankmateFieldSet.width = TANKMATE_CONTENT_WIDTH - 4;
         this.tankmateFieldSet.height = TANKMATE_CONTENT_HEIGHT - 36;
         this.tankmateFieldSet.showLabel = false;
         this.tankmatePane.addChild(this.tankmateFieldSet);

         this.tankmateInnerTabs = this.makeTankmateComponent("ButtonBarEx") as ButtonBarEx;
         var providerClass:Class = getDefinitionByName("scaleform.clik.data.DataProvider") as Class;
         this.tankmateInnerTabs.itemRendererName = "SmallTabButton";
         this.tankmateInnerTabs.dataProvider = new providerClass([{label:"Tankmate Signal"}]);
         this.tankmateInnerTabs.selectedIndex = 0;
         this.tankmateInnerTabs.autoSize = "right";
         this.tankmateInnerTabs.paddingHorizontal = 15;
         this.tankmateInnerTabs.x = 2;
         this.tankmateInnerTabs.y = 0;
         this.tankmateInnerTabs.width = TANKMATE_CONTENT_WIDTH - 4;
         this.tankmateInnerTabs.height = 28;
         this.tankmatePane.addChild(this.tankmateInnerTabs);

         this.tankmateLabel = this.makeTankmateText();
         this.tankmateLabel.x = 24;
         this.tankmateLabel.y = 65;
         this.tankmateLabel.width = 350;
         this.tankmateLabel.height = 28;
         this.tankmatePane.addChild(this.tankmateLabel);

         this.tankmateKey = this.makeTankmateComponent("KeyInputUI") as KeyInput;
         this.tankmateKey.x = 414;
         this.tankmateKey.y = 62;
         this.tankmatePane.addChild(this.tankmateKey);
         this.tankmateKey.addEventListener(Event.SELECT, this.onTankmateCapture, false, 0, true);
         this.tankmateKey.validateNow();
         this.tankmateKey.keys = [];

         this.tankmateDeveloper = this.makeTankmateComponent("CheckBox") as CheckBox;
         this.tankmateDeveloper.x = 24;
         this.tankmateDeveloper.y = 112;
         this.tankmateDeveloper.width = 550;
         this.tankmatePane.addChild(this.tankmateDeveloper);
         this.tankmateDeveloper.addEventListener(Event.SELECT, this.onTankmateDeveloper, false, 0, true);

         this.tankmateDescription = this.makeTankmateText();
         this.tankmateDescription.x = 44;
         this.tankmateDescription.y = 140;
         this.tankmateDescription.width = 650;
         this.tankmateDescription.height = 60;
         this.tankmateDescription.multiline = true;
         this.tankmateDescription.wordWrap = true;
         this.tankmatePane.addChild(this.tankmateDescription);
         var underline:Object = this.makeTankmateComponent("KeyItemUnderlineUI");
         underline.x = 24;
         underline.y = 96;
         underline.width = TANKMATE_CONTENT_WIDTH - 48;
         this.tankmatePane.addChild(underline);
         this.syncTankmateControls();
      }

      private function tankmateTabIndex() : int
      {
         if(tabs.dataProvider == null)
         {
            return -1;
         }
         for(var i:int = 0; i < tabs.dataProvider.length; i++)
         {
            if(tabs.dataProvider[i].alias == "tankmateMods")
            {
               return i;
            }
         }
         return -1;
      }

      private function installTankmateTab() : void
      {
         if(tabs.dataProvider != null && this.tankmateTabIndex() == -1)
         {
            tabs.dataProvider.push(new TabsDataVo({label:"Mods", linkage:"tankmateMods", alias:"tankmateMods"}));
            tabs.dataProvider.invalidate();
         }
      }

      private function onTankmateTab(event:Event) : void
      {
         var index:int = this.tankmateTabIndex();
         if(this.tankmateSync || (index >= 0 && tabs.selectedIndex == index))
         {
            event.stopImmediatePropagation();
            if(!this.tankmateSync)
            {
               this.showTankmate(true);
            }
            return;
         }
         this.showTankmate(false);
      }

      private function showTankmate(active:Boolean) : void
      {
         this.tankmateActive = active;
         if(active && this.tankmatePane == null && this.tankmateHooksReady)
         {
            this.buildTankmatePane();
         }
         if(this.tankmatePane != null)
         {
            this.tankmatePane.visible = active;
         }
         view.visible = !active;
         if(!active && this.tankmateCapture)
         {
            this.tankmateCapture = false;
            onSettingsChangeS(TANKMATE_LINK, {action:"cancel_capture"});
         }
      }

      private function syncTankmateControls() : void
      {
         if(this.tankmatePane == null || this.tankmateState == null)
         {
            return;
         }
         this.tankmateSync = true;
         this.tankmateLabel.text = this.tankmateState.hotkeyLabel;
         this.tankmateDeveloper.label = this.tankmateState.devLabel;
         this.tankmateDeveloper.selected = Boolean(this.tankmateState.dev_mode);
         this.tankmateDescription.text = this.tankmateState.devDescription;
         this.tankmateKey.selected = this.tankmateCapture;
         this.tankmateKey.label = this.tankmateState.shortcutLabel;
         this.tankmateKey.validateNow();
         this.tankmateKey.textField.text = this.tankmateState.shortcutLabel;
         this.tankmateKey.alert.visible = false;
         this.tankmateSync = false;
      }

      private function onTankmateCapture(event:Event) : void
      {
         if(!this.tankmateSync)
         {
            this.tankmateCapture = Boolean(this.tankmateKey.selected);
            onSettingsChangeS(TANKMATE_LINK, {action:this.tankmateCapture ? "capture" : "cancel_capture"});
         }
      }

      private function onTankmateDeveloper(event:Event) : void
      {
         if(!this.tankmateSync)
         {
            onSettingsChangeS(TANKMATE_LINK, {action:"dev_mode", value:Boolean(this.tankmateDeveloper.selected)});
         }
      }

      private function onTankmateInput(event:Event) : void
      {
         if(this.tankmateActive && this.tankmateCapture)
         {
            event.preventDefault();
            event.stopImmediatePropagation();
            var details:Object = Object(event).details;
            if(details.value == "keyDown")
            {
               onSettingsChangeS(TANKMATE_LINK, {action:"key", code:Number(details.code)});
            }
         }
      }

      private function onTankmateFrame(event:Event) : void
      {
         this.installTankmateTab();
         if(this.tankmateActive)
         {
            view.visible = false;
         }
         if(this.tankmateDirty)
         {
            applyBtn.enabled = true;
         }
         if(this.tankmatePane != null && this.tankmateState != null)
         {
            this.tankmateKey.textField.text = this.tankmateState.shortcutLabel;
            this.tankmateKey.alert.visible = false;
         }
      }

      override protected function onDispose() : void
      {
         removeEventListener(Event.ENTER_FRAME, this.onTankmateFrame);
         tabs.removeEventListener(IndexEvent.INDEX_CHANGE, this.onTankmateTab);
         if(this.tankmateInputManager != null)
         {
            this.tankmateInputManager.removeEventListener("input", this.onTankmateInput);
            this.tankmateInputManager = null;
         }
         if(this.tankmatePane != null)
         {
            this.tankmateKey.removeEventListener(Event.SELECT, this.onTankmateCapture);
            this.tankmateDeveloper.removeEventListener(Event.SELECT, this.onTankmateDeveloper);
            this.tankmateKey.dispose();
            this.tankmateDeveloper.dispose();
            this.tankmateInnerTabs.dispose();
            this.tankmateFieldSet.dispose();
            removeChild(this.tankmatePane);
            this.tankmatePane = null;
         }
         super.onDispose();
      }

      // Injected into the stock dialog; the builder gives its root a unique name.
      private static const CONTENT_WIDTH:Number = 720;
      private static const CONTENT_HEIGHT:Number = 400;
      private static const DESIGN_WIDTH:Number = 1760;
      private static const BUTTON_WIDTH:Number = 160;
      private static const BUTTON_HEIGHT:Number = 32;
      private static const VIEWPORT_MARGIN:Number = 24;
      private var fitScale:Number = 1;
      private var welcomeContent:Sprite;
      private var welcomeImages:Array = [];

      override public function get width() : Number
      {
         return Math.floor(CONTENT_WIDTH * fitScale);
      }

      override protected function getBackgroundActualHeight() : Number
      {
         return 336 * fitScale;
      }

      override public function get height() : Number
      {
         return Math.floor(CONTENT_HEIGHT * fitScale);
      }

      override public function as_setTitle(value:String) : void
      {
         super.as_setTitle("");
      }

      override public function updateStage(stageWidth:Number, stageHeight:Number) : void
      {
         if(window != null && stageWidth > 0 && stageHeight > 0)
         {
            var availableWidth:Number = stageWidth - App.utils.viewRestrictions.horizontalOffset
                                        - window.contentPadding.horizontal - VIEWPORT_MARGIN;
            var availableHeight:Number = stageHeight - App.utils.viewRestrictions.verticalOffset
                                         - window.contentPadding.vertical - VIEWPORT_MARGIN;
            var nextScale:Number = Math.min(1, availableWidth / CONTENT_WIDTH,
                                             availableHeight / CONTENT_HEIGHT);
            if(nextScale > 0 && nextScale != fitScale)
            {
               fitScale = nextScale;
               if(welcomeContent != null)
               {
                  welcomeContent.scaleX = welcomeContent.scaleY = width / DESIGN_WIDTH;
                  sizeWelcomeButton();
               }
               invalidateLayout();
            }
         }
         super.updateStage(stageWidth, stageHeight);
      }

      override protected function applyLayout() : void
      {
         textField.visible = false;
         super.applyLayout();
         thirdBtn.x = Math.round((width - thirdBtn.width) / 2);
         thirdBtn.y = Math.round(352 * fitScale);
      }

      private function sizeWelcomeButton() : void
      {
         thirdBtn.setSize(Math.round(BUTTON_WIDTH * fitScale), Math.round(BUTTON_HEIGHT * fitScale));
         thirdBtn.validateNow();
      }

      private function welcomeText(value:String, xPos:Number, yPos:Number, wide:Number,
                                   high:Number, size:Number = 34, title:Boolean = false) : TextField
      {
         var field:TextField = new TextField();
         var format:TextFormat = new TextFormat(title ? "$TitleFont" : "$TextFont", size,
                                               title ? 0xF0E2C0 : 0xD2C3A1);
         format.align = "left";
         format.leading = 4;
         field.defaultTextFormat = format;
         field.embedFonts = true;
         field.selectable = false;
         field.mouseEnabled = false;
         field.multiline = true;
         field.wordWrap = true;
         field.x = xPos;
         field.y = yPos;
         field.width = wide;
         field.height = high;
         field.text = value;
         this.welcomeContent.addChild(field);
         return field;
      }

      private function welcomeImage(path:String, xPos:Number, yPos:Number,
                                    wide:Number, high:Number) : Image
      {
         var image:Image = new Image();
         image.x = xPos;
         image.y = yPos;
         image.mouseEnabled = false;
         image.mouseChildren = false;
         image.smoothing = true;
         this.welcomeImages.push({image:image, wide:wide, high:high});
         image.addEventListener(Event.CHANGE, this.onWelcomeImage, false, 0, true);
         this.welcomeContent.addChild(image);
         image.source = "img://" + path;
         if(image.ready)
         {
            image.width = wide;
            image.height = high;
         }
         return image;
      }

      private function onWelcomeImage(event:Event) : void
      {
         for each(var item:Object in this.welcomeImages)
         {
            if(item.image == event.currentTarget && item.image.ready)
            {
               item.image.width = item.wide;
               item.image.height = item.high;
            }
         }
      }

      public function as_setTankmateWelcome(data:Object) : void
      {
         if(this.welcomeContent != null)
         {
            return;
         }
         this.welcomeContent = new Sprite();
         this.welcomeContent.scaleX = this.welcomeContent.scaleY = width / DESIGN_WIDTH;
         thirdBtn.dynamicSizeByText = false;
         thirdBtn.useHtmlText = true;
         thirdBtn.label = '<font face="$TitleFont" size="15" color="#F0E2C0">' + data.gotIt + '</font>';
         thirdBtn.textField.autoSize = "center";
         thirdBtn.usePreventUpdateTextScale = true;
         thirdBtn.textYPadding = -1;
         thirdBtn.bgMc.transform.colorTransform = new ColorTransform(1.05, 0.72, 0.4, 1, 18, 2, 0);
         sizeWelcomeButton();
         this.welcomeContent.mouseEnabled = false;
         this.welcomeContent.mouseChildren = false;
         addChild(this.welcomeContent);
         this.welcomeContent.graphics.beginFill(0, 0);
         this.welcomeContent.graphics.drawRect(0, 0, 1760, 820);
         this.welcomeContent.graphics.endFill();
         this.welcomeContent.graphics.beginFill(0x666342, 0.16);
         this.welcomeContent.graphics.drawRect(0, 0, 1760, 300);
         this.welcomeContent.graphics.endFill();
         this.welcomeContent.graphics.lineStyle(1, 0xC7B78E, 0.6);
         this.welcomeContent.graphics.moveTo(48, 300);
         this.welcomeContent.graphics.lineTo(1712, 300);
         this.welcomeContent.graphics.moveTo(0, 820);
         this.welcomeContent.graphics.lineTo(1760, 820);
         this.welcomeContent.graphics.lineStyle(1, 0xC7B78E, 0.3);
         this.welcomeContent.graphics.moveTo(574, 346);
         this.welcomeContent.graphics.lineTo(574, 786);
         this.welcomeContent.graphics.moveTo(1186, 346);
         this.welcomeContent.graphics.lineTo(1186, 786);

         this.welcomeText("Tankmate Signal", 72, 58, 760, 112, 88, true);
         this.welcomeText(data.intro, 76, 174, 770, 100, 39);

         // The preview uses the real banner's textures and relative proportions.
         var firstBannerChild:int = welcomeContent.numChildren;
         var base:String = "gui/maps/icons/tankmate_signal/";
         this.welcomeImage(base + "plate.png", 980, 96, 720, 144);
         this.welcomeImage(base + "profile-online.png", 1002, 131, 74, 74);
         var rule:Image = this.welcomeImage(base + "status-rule.png", 1097, 162, 209, 3);
         rule.transform.colorTransform = new ColorTransform(0, 0, 0, 1, 156, 194, 128);
         this.welcomeText("IronFox_7", 1097, 112, 180, 42, 28);
         this.welcomeText("[WOLF]", 1280, 118, 130, 40, 24);
         this.welcomeImage(data.statusImage, 1097, 179, 246, 34);
         this.welcomeImage(data.buttonImage, 1460, 96, 240, 144);
         if(data.shortcut.length > 0)
         {
            this.welcomeImage(base + "shortcut-keycap.png", 1506, 181, 154, 37);
            var key:TextField = this.welcomeText(data.shortcut, 1510, 182, 146, 36, 24);
            var centered:TextFormat = key.defaultTextFormat;
            centered.align = "center";
            key.setTextFormat(centered);
         }
         var banner:Sprite = new Sprite();
         while(welcomeContent.numChildren > firstBannerChild)
         {
            banner.addChild(welcomeContent.getChildAt(firstBannerChild));
         }
         // The live online plate is at least 412 x 84 at its reference UI scale.
         var bannerScale:Number = Math.min(1.15, 412 / (720 * CONTENT_WIDTH / DESIGN_WIDTH),
                                            84 / (144 * CONTENT_WIDTH / DESIGN_WIDTH));
         banner.scaleX = banner.scaleY = bannerScale;
         banner.x = 1700 - 1700 * bannerScale;
         banner.y = 168 - 168 * bannerScale;
         welcomeContent.addChild(banner);

         var positions:Array = [72, 632, 1244];
         var bodies:Array = [data.alerts, data.message, data.settings];
         for(var i:int = 0; i < 3; i++)
         {
            var badge:Sprite = new Sprite();
            var gradient:Matrix = new Matrix();
            gradient.createGradientBox(66, 46, Math.PI / 2);
            badge.graphics.lineStyle(1, 0xC7AB76, 0.95);
            badge.graphics.beginGradientFill("linear", [0x9B7745, 0x3B2A16], [1, 1], [0, 255], gradient);
            badge.graphics.moveTo(12, 0);
            badge.graphics.lineTo(66, 0);
            badge.graphics.lineTo(66, 32);
            badge.graphics.lineTo(54, 46);
            badge.graphics.lineTo(0, 46);
            badge.graphics.lineTo(0, 14);
            badge.graphics.lineTo(12, 0);
            badge.graphics.endFill();
            badge.x = positions[i];
            badge.y = 346;
            this.welcomeContent.addChild(badge);
            var number:TextField = this.welcomeText(String(i + 1), positions[i], 342, 66, 54, 40, true);
            var numberFormat:TextFormat = number.defaultTextFormat;
            numberFormat.align = "center";
            number.setTextFormat(numberFormat);
            this.welcomeText(data.headings[i], positions[i] + 94, 344, i == 0 ? 400 : 420, 112, 44, true);
            var bodyWidth:Number = i == 0 ? 470 : 490;
            var body:TextField = this.welcomeText(bodies[i], positions[i] + 20, 458, bodyWidth, 220, 39);
            if(i == 1)
            {
               body.autoSize = "left";
               this.welcomeText(data.battle, body.x, body.y + body.height + 16, bodyWidth, 132, 34);
            }
         }
         invalidateLayout();
         updateStage(App.appWidth, App.appHeight);
      }

      override protected function onDispose() : void
      {
         for each(var item:Object in this.welcomeImages)
         {
            item.image.removeEventListener(Event.CHANGE, this.onWelcomeImage);
            item.image.dispose();
         }
         this.welcomeImages = [];
         if(this.welcomeContent != null)
         {
            removeChild(this.welcomeContent);
            this.welcomeContent = null;
         }
         super.onDispose();
      }

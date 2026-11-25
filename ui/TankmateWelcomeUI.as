      // Injected into the stock dialog; the builder gives its root a unique name.
      private var welcomeContent:Sprite;
      private var welcomeImages:Array = [];

      override public function get width() : Number
      {
         return 1040;
      }

      override protected function getBackgroundActualHeight() : Number
      {
         return 350;
      }

      override protected function applyLayout() : void
      {
         textField.visible = false;
         textField.width = 1040;
         super.applyLayout();
      }

      private function welcomeText(value:String, xPos:Number, yPos:Number, wide:Number,
                                   high:Number, size:Number = 16, title:Boolean = false) : TextField
      {
         var field:TextField = new TextField();
         var format:TextFormat = new TextFormat(title ? "$TitleFont" : "$TextFont", size,
                                               title ? 0xEEEDE9 : 0xD1CBBC);
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
         this.welcomeContent.mouseEnabled = false;
         this.welcomeContent.mouseChildren = false;
         addChild(this.welcomeContent);
         this.welcomeContent.graphics.beginFill(0, 0);
         this.welcomeContent.graphics.drawRect(0, 0, 1040, 350);
         this.welcomeContent.graphics.endFill();
         this.welcomeContent.graphics.lineStyle(1, 0xB2AA98, 0.24);
         this.welcomeContent.graphics.moveTo(32, 148);
         this.welcomeContent.graphics.lineTo(1008, 148);
         this.welcomeContent.graphics.moveTo(354, 176);
         this.welcomeContent.graphics.lineTo(354, 340);
         this.welcomeContent.graphics.moveTo(692, 176);
         this.welcomeContent.graphics.lineTo(692, 340);
         this.welcomeText("Tankmate Signal", 32, 30, 480, 48, 30, true);
         this.welcomeText(data.intro, 32, 88, 460, 48, 18);

         // Use exactly the same textures and component arrangement as NotificationPlate.
         var base:String = "gui/maps/icons/tankmate_signal/";
         this.welcomeImage(base + "plate.png", 540, 32, 468, 94);
         this.welcomeImage(base + "profile-online.png", 554, 55, 48, 48);
         var rule:Image = this.welcomeImage(base + "status-rule.png", 616, 75, 136, 2);
         rule.transform.colorTransform = new ColorTransform(0, 0, 0, 1, 156, 194, 128);
         this.welcomeText("IronFox7", 616, 43, 108, 30, 18, true);
         this.welcomeText("[WOLF]", 728, 47, 80, 26, 14);
         this.welcomeImage(data.statusImage, 616, 86, 160, 22);
         this.welcomeImage(data.buttonImage, 852, 32, 156, 94);
         if(data.shortcut.length > 0)
         {
            this.welcomeImage(base + "shortcut-keycap.png", 882, 87, 100, 24);
            var key:TextField = this.welcomeText(data.shortcut, 884, 88, 96, 24, 14);
            var centered:TextFormat = key.defaultTextFormat;
            centered.align = "center";
            key.setTextFormat(centered);
         }
         var positions:Array = [32, 370, 708];
         var bodies:Array = [data.alerts, data.message, data.settings];
         for(var i:int = 0; i < 3; i++)
         {
            this.welcomeText(data.headings[i], positions[i], 176, 300, 50, 22, true);
            this.welcomeText(bodies[i], positions[i], 234, 300, 76, 16);
         }
         this.welcomeText(data.battle, 370, 314, 300, 36, 14);
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

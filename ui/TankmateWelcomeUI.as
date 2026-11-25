      // Injected into the stock dialog; the builder gives its root a unique name.
      private var welcomeContent:Sprite;
      private var welcomeImages:Array = [];

      override public function get width() : Number
      {
         return 1040;
      }

      override protected function getBackgroundActualHeight() : Number
      {
         return 300;
      }

      override protected function applyLayout() : void
      {
         textField.visible = false;
         textField.width = 1040;
         setSize(1040, 330);
         super.applyLayout();
      }

      private function welcomeText(value:String, xPos:Number, yPos:Number, wide:Number,
                                   high:Number, size:Number = 14, title:Boolean = false) : TextField
      {
         var field:TextField = new TextField();
         var format:TextFormat = new TextFormat(title ? "$TitleFont" : "$TextFont", size,
                                               title ? 0xEEEDE9 : 0xB2AA98);
         format.align = "left";
         format.leading = 3;
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
         this.welcomeContent.graphics.drawRect(0, 0, 1040, 300);
         this.welcomeContent.graphics.endFill();
         this.welcomeContent.graphics.lineStyle(1, 0xB2AA98, 0.35);
         this.welcomeContent.graphics.moveTo(20, 132);
         this.welcomeContent.graphics.lineTo(1020, 132);
         this.welcomeContent.graphics.moveTo(346, 158);
         this.welcomeContent.graphics.lineTo(346, 275);
         this.welcomeContent.graphics.moveTo(684, 158);
         this.welcomeContent.graphics.lineTo(684, 275);
         this.welcomeText("Tankmate Signal", 22, 22, 490, 45, 28, true);
         this.welcomeText(data.intro, 22, 70, 490, 45, 16);

         // Use exactly the same textures and component arrangement as NotificationPlate.
         var base:String = "gui/maps/icons/tankmate_signal/";
         this.welcomeImage(base + "plate.png", 550, 18, 468, 94);
         this.welcomeImage(base + "profile-online.png", 564, 41, 48, 48);
         var rule:Image = this.welcomeImage(base + "status-rule.png", 626, 61, 136, 2);
         rule.transform.colorTransform = new ColorTransform(0, 0, 0, 1, 156, 194, 128);
         this.welcomeText("IronFox_7", 626, 30, 105, 28, 16, true);
         this.welcomeText("[WOLF]", 731, 33, 85, 28, 14);
         this.welcomeImage(data.statusImage, 626, 72, 160, 22);
         this.welcomeImage(data.buttonImage, 862, 18, 156, 94);
         if(data.shortcut.length > 0)
         {
            this.welcomeImage(base + "shortcut-keycap.png", 913, 73, 78, 22);
            var key:TextField = this.welcomeText(data.shortcut, 915, 75, 74, 20, 12);
            var centered:TextFormat = key.defaultTextFormat;
            centered.align = "center";
            key.setTextFormat(centered);
         }
         var positions:Array = [22, 364, 702];
         var bodies:Array = [data.alerts, data.message, data.settings];
         for(var i:int = 0; i < 3; i++)
         {
            this.welcomeText(String(i + 1), positions[i], 158, 26, 30, 18, true);
            this.welcomeText(data.headings[i], positions[i] + 32, 158, 282, 50, 18, true);
            this.welcomeText(bodies[i], positions[i] + 8, 207, 304, 65, 14);
         }
         this.welcomeText(data.battle, 372, 268, 302, 32, 12);
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

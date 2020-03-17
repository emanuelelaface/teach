from remi.gui import *
from remi import start, App
import os
import io
import PyPDF2
from wand.image import Image
import base64
import magic
import time

students = {}
students['default'] = {}
professor = '192.168.212'
view_box_width = '1024'
view_box_height = '768'
lecture_started = False

class MySvg(Svg):
    @decorate_set_on_listener("(self, emitter, x, y)")
    @decorate_event_js("""var params={};
            var pt = this.createSVGPoint();
            pt.x = event.clientX;
            pt.y = event.clientY
            var loc = pt.matrixTransform(this.getScreenCTM().inverse());
            params['x']=loc.x;
            params['y']=loc.y;
            sendCallbackParam('%(emitter_identifier)s','%(event_name)s',params);""")
    def onmousemove(self, x, y):
        return (x, y)
    @decorate_set_on_listener("(self, emitter, x, y)")
    @decorate_event_js("""var params={};
            var pt = this.createSVGPoint();
            pt.x = parseInt(event.changedTouches[0].clientX)
            pt.y = parseInt(event.changedTouches[0].clientY)
            var loc = pt.matrixTransform(this.getScreenCTM().inverse());
            params['x']=loc.x;
            params['y']=loc.y;
            sendCallbackParam('%(emitter_identifier)s','%(event_name)s',params);""")
    def ontouchmove(self, x, y):
        return (x, y)

class Teach(App):
    def __init__(self, *args, **kwargs):
        super(Teach, self).__init__(*args, static_file_path={'my_res':'/opt/teach/res/'})

    def idle(self):
        global students
        global lecture_started
        if not professor in self.client_address[0] and students[self.client_address[0]]['update']:
            self.set_root_widget(students['default']['svg'])
            students[self.client_address[0]]['update'] = False

    def main(self):
        global students
        global lecture_started
        self.page.children['body'].style['overflow'] = 'hidden'
        if professor in str(self.client_address[0]):
            self.frames = {}
            return self.upload_file()
        else:
            if not lecture_started:
                students[self.client_address[0]]={'update': False}
                return HBox([Label('Waiting for Professor', style={'margin': '0px', 'font-size': 'large', 'padding': '100px', 'background': 'lime', 'text-align': 'center'})], style={'background': 'lime'})
            else:
                students[self.client_address[0]]={'update': False}
                return students['default']['svg']

    def set_main_screen(self, widget, filename):
        global students
        global lecture_started
        if 'pdf' in magic.from_file(filename, mime=True).lower():
            self.inputfilename = filename
            self.inputfile = open(filename, 'rb')
            self.pdf_file = PyPDF2.PdfFileReader(self.inputfile)
            self.svg = MySvg()
            self.svg.attr_viewBox = "0,0,"+view_box_width+','+view_box_height
            self.svg.style.update({'width':'100%', 'height':'100%'})
            self.svg.style.update({'cursor': 'url(/my_res:cursor-black.png), auto'})
            self.write = False
            self.svg.attributes['tabindex'] = '1'
            self.svg.onmousedown.do(self.write_on)
            self.svg.onmouseup.do(self.write_off)
            self.svg.onmousemove.do(self.draw)
            self.svg.ontouchstart.do(self.write_on)
            self.svg.ontouchend.do(self.write_off)
            self.svg.ontouchmove.do(self.draw)
            self.svg.onkeyup.do(self.keyboard_opts)
            self.current_page = 0
            self.lines = []
            self.color = 'black'
            students['default']['svg']=MySvg()
            students['default']['svg'].attr_viewBox = "0,0,"+view_box_width+','+view_box_height
            students['default']['svg'].style.update({'width':'100%', 'height':'100%'})
            for IP in students:
                students[IP]['update'] = False

            self.set_pdf_page(self.current_page)
            self.set_root_widget(self.svg)
            lecture_started = True
        else:
            os.remove(filename)
            self.set_root_widget(HBox([Label('ERROR: Invalid PDF', style={'margin': '0px', 'font-size': 'large', 'padding': '100px', 'background': 'red', 'text-align': 'center'})], style={'background': 'red'}))
            time.sleep(3)
            self.set_root_widget(self.upload_file())

    def set_pdf_page(self, page_number):
        global students
        tmp_pdf = PyPDF2.PdfFileWriter()
        tmp_pdf.addPage(self.pdf_file.getPage(page_number))
        page = io.BytesIO()
        tmp_pdf.write(page)
        page.seek(0)
        png_image = Image(file = page, resolution = 300)
        img_buffer = base64.b64encode(png_image.make_blob('png')).decode('utf-8')
        svg_image = SvgImage(image_data='data:image/png;base64, '+img_buffer)
        svg_image.style.update({'width':'100%', 'height':'100%'})
        svg_image.attr_width = view_box_width
        svg_image.attr_height = view_box_height
        self.svg.append(svg_image, 'pdf_page')
        self.draw_element = 0
        students['default']['svg'].append(svg_image)
        for IP in students:
            students[IP]['update'] = True

    def keyboard_opts(self, emitter, key, keycode, ctrl, shift, alt):
        global students
        if key == 'c':
            color_list = ['black', 'red', 'green', 'blue', 'yellow']
            color_index = color_list.index(self.color)
            self.color = color_list[(color_index+1)%len(color_list)]
            self.svg.style.update({'cursor': 'url(/my_res:cursor-'+self.color+'.png), auto'})
        if key == 'Backspace' and self.draw_element > 0:
            self.svg.append(SvgPolyline(), str(self.draw_element))
            self.lines.pop()
            students['default']['svg'].append(SvgPolyline(), str(self.draw_element))
            for IP in students:
                students[IP]['update'] = True
            self.draw_element -= 1
        if key == 'ArrowLeft' and self.current_page > 0:
            self.current_page -= 1
            self.set_pdf_page(self.current_page)
            self.draw_element = 0
            for line in self.lines:
                self.draw_element += 1
                self.svg.append(line, str(self.draw_element))
                students['default']['svg'].append(line, str(self.draw_element))
            for IP in students:
                students[IP]['update'] = True
        if key == 'ArrowRight' and self.current_page < self.pdf_file.getNumPages()-1:
            self.current_page += 1
            self.set_pdf_page(self.current_page)
            self.draw_element = 0
            for line in self.lines:
                self.draw_element += 1
                self.svg.append(line, str(self.draw_element))
                students['default']['svg'].append(line, str(self.draw_element))
            for IP in students:
                students[IP]['update'] = True
        if key == ' ':
            for i in range(self.draw_element):
                self.svg.append(SvgPolyline(), str(i+1))
                students['default']['svg'].append(SvgPolyline(), str(i+1))
            for IP in students:
                    students[IP]['update'] = True
            self.draw_element = 0 
            self.lines=[]
        if key == 'q':
            os.remove(self.inputfilename)
            self.inputfile.close()
            self.close()

    def upload_file(self):
        upload_file = FileUploader(style={'margin': '0px', 'font-size': 'large', 'padding': '100px', 'background': 'lime'})
        upload_file.onsuccess.do(self.set_main_screen)
        return HBox([upload_file], style={'background': 'lime'})

    def draw(self, emitter, x, y):
        if self.write:
            self.line.add_coord(x,y)
        
    def write_on(self, emitter, x, y):
        self.draw_element += 1
        self.line = SvgPolyline()
        self.line.set_stroke(width=2, color=self.color)
        self.line.set_fill(None)
        self.lines.append(self.line)
        self.svg.append(self.line, str(self.draw_element))
        self.write = True

    def write_off(self, emitter, x, y):
        global students
        self.write = False
        draw_element = 0
        for line in self.lines:
            draw_element += 1
            students['default']['svg'].append(line, str(draw_element))
        for IP in students:
            students[IP]['update'] = True

if __name__ == "__main__":
    start(Teach, address='0.0.0.0', port=8081, start_browser=False, username=None, password=None, multiple_instance=True)

import urllib, math
from sys import stdout

class FilePuller():
	@classmethod
	def save(cls,remote,local):
		# open stream to remote path
		request = urllib.urlopen(remote)


		total_size = int(request.info().getheader('Content-Length').strip())

		downloaded = 0
		CHUNK = 256 * 10240

		with open(local,'wb') as fp:
			while True:
				chunk = request.read(CHUNK)
				downloaded += len(chunk)
				stdout.write("Downloaded {percentage}%\n".format(percentage = str(math.floor( (downloaded / total_size) * 100))))
				if not chunk:
					break
				fp.write(chunk)